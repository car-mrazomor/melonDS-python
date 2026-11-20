"""PymelonDS: a PyBoy-style API for the melonDS Nintendo DS emulator."""

import heapq
import io
import itertools
import operator
from pathlib import Path

from PIL import Image

from . import _bindings as _b
from .exceptions import PymelonDSInvalidInputException, PymelonDSInvalidOperationException

WINDOWS = ("null", "headless", "dummy", "SDL2")

BUTTONS = {
    "a": _b.KEY_A,
    "b": _b.KEY_B,
    "x": _b.KEY_X,
    "y": _b.KEY_Y,
    "l": _b.KEY_L,
    "r": _b.KEY_R,
    "start": _b.KEY_START,
    "select": _b.KEY_SELECT,
    "up": _b.KEY_UP,
    "down": _b.KEY_DOWN,
    "left": _b.KEY_LEFT,
    "right": _b.KEY_RIGHT,
}


class _ScreenView:
    """One rendered surface: a live view over the frame buffer."""

    def __init__(self, buffer: memoryview, width: int, height: int):
        self.raw_buffer = buffer
        self.raw_buffer_dims = (height, width)
        self.raw_buffer_format = "RGBA"
        self._image = None
        self._make_image()

    def _make_image(self) -> None:
        self._image = Image.frombuffer(
            "RGBA", (self.raw_buffer_dims[1], self.raw_buffer_dims[0]), self.raw_buffer, "raw", "RGBA", 0, 1
        )

    def _post_tick(self) -> None:
        # PIL copies the data on write (e.g. after some operations); reconnect to the live buffer.
        if not self._image.readonly:
            self._make_image()

    @property
    def image(self) -> Image.Image:
        """PIL Image (RGBA). Live: its contents change after every rendered tick. Copy it to keep a frame."""
        return self._image


class Screen(_ScreenView):
    """Both screens stacked (top above bottom), 256x384. `.top` / `.bottom` are 256x192 each."""

    def __init__(self):
        w, h = _b.SCREEN_WIDTH, _b.SCREEN_HEIGHT
        self._buffer = bytearray(_b.SCREEN_BYTES * 2)
        mv = memoryview(self._buffer)
        super().__init__(mv, w, h * 2)
        self.top = _ScreenView(mv[: _b.SCREEN_BYTES], w, h)
        self.bottom = _ScreenView(mv[_b.SCREEN_BYTES :], w, h)

    def _update(self, core: "_b.Core") -> None:
        core.screens_into(self.top.raw_buffer, self.bottom.raw_buffer)
        self._post_tick()
        self.top._post_tick()
        self.bottom._post_tick()


def _check_state_file(file_like_object, what: str) -> None:
    if isinstance(file_like_object, (str, Path)):
        raise PymelonDSInvalidInputException(
            f"{what} takes a file-like object, not a path. Did you specify a filepath instead of open(..., 'wb'/'rb')?"
        )
    if isinstance(file_like_object, io.TextIOBase):
        raise PymelonDSInvalidInputException(f"{what} needs a binary file; open it with 'wb' / 'rb'")


class PymelonDS:
    def __init__(self, gamerom, *, sav_file=None, bios9=None, bios7=None, firmware=None, jit=True,
                 window="null", scale=2):
        """
        gamerom:  path to a .nds ROM, or a binary file-like object (anything with .read())
        sav_file: battery save to load (and write on stop). Defaults to the ROM path with .sav;
                  None if gamerom is a file object, in which case no battery save is used.
        bios9, bios7, firmware: optional dumps; FreeBIOS and generated firmware are used otherwise
        jit: use the JIT recompiler
        window: "null" (no window, default; "headless"/"dummy" are aliases) or "SDL2" (needs pysdl2)
        scale: window scale factor (SDL2 only)
        """
        self.stopped = True
        self._window = None
        if window not in WINDOWS:
            raise PymelonDSInvalidInputException(f"Unknown window type: {window!r}. Use one of {WINDOWS}")
        try:
            scale = operator.index(scale)
        except TypeError:
            raise PymelonDSInvalidInputException("scale must be a positive integer") from None
        if scale < 1:
            raise PymelonDSInvalidInputException("scale must be a positive integer")
        if gamerom is None:
            raise FileNotFoundError("None is not a ROM path")

        rom_data = None
        if isinstance(gamerom, (str, Path)):
            self.gamerom = str(gamerom)
            if not Path(self.gamerom).is_file():
                raise FileNotFoundError(f"ROM file {self.gamerom} was not found!")
        elif hasattr(gamerom, "read"):
            self.gamerom = None
            rom_data = gamerom.read()
            if not isinstance(rom_data, (bytes, bytearray, memoryview)):
                raise PymelonDSInvalidInputException("gamerom file object must be opened in binary mode ('rb')")
            if len(rom_data) == 0:
                raise PymelonDSInvalidInputException("gamerom file object is empty")
        else:
            raise PymelonDSInvalidInputException("gamerom must be a path (str or Path) or a binary file-like object")

        for p in (bios9, bios7, firmware):
            if p is not None and not Path(p).is_file():
                raise FileNotFoundError(f"File {p} was not found!")

        if sav_file is not None:
            self.sav_file = str(sav_file)
        elif self.gamerom is not None:
            self.sav_file = str(Path(self.gamerom).with_suffix(".sav"))
        else:
            self.sav_file = None

        self._core = _b.Core(bios9=bios9, bios7=bios7, firmware=firmware, jit=jit)
        if rom_data is None:
            self._core.load_rom(self.gamerom, self.sav_file)
        else:
            self._core.load_rom_bytes(rom_data, self.sav_file)

        self.frame_count = 0
        self.screen = Screen()
        self.screen._update(self._core)

        self._keys = 0
        self._applied_keys = 0
        self._quitting = False
        self._events = []           # (mask, pressed) applied at the start of the next frame
        self._delayed = []          # heap of (frame, seq, (mask, pressed))
        self._seq = itertools.count()

        from .window import FrameLimiter

        if window == "SDL2":
            from .window import SDL2Window

            title = "PymelonDS" + (f" - {Path(self.gamerom).name}" if self.gamerom else "")
            self._window = SDL2Window(scale, title, BUTTONS)
            self._limiter = FrameLimiter(1)
        else:
            self._limiter = FrameLimiter(0)
        self.stopped = False

    # ---- emulation ----------------------------------------------------------

    def tick(self, count=1, render=True) -> bool:
        """Run `count` frames. The screen is updated after the last one if `render` is True."""
        if self.stopped:
            raise PymelonDSInvalidOperationException("Emulator is stopped")
        try:
            count = operator.index(count)
        except TypeError:
            raise PymelonDSInvalidInputException("count must be a non-negative integer") from None
        if count < 0:
            raise PymelonDSInvalidInputException("count must be a non-negative integer")

        win = self._window
        for _ in range(count):
            self._handle_events()
            if win is not None:
                win.poll(self._core)
                if win.quit:
                    self._quitting = True
            self._apply_keys()
            self._core.run_frame()
            self.frame_count += 1
            self._post_handle_events()
            if win is not None:
                win.present(self._core)
            self._limiter.wait()

        if render and count > 0:
            self.screen._update(self._core)
        return not self._quitting

    def _handle_events(self) -> None:
        if not self._events:
            return
        keys = self._keys
        for mask, pressed in self._events:
            keys = (keys | mask) if pressed else (keys & ~mask)
        self._events.clear()
        self._keys = keys

    def _apply_keys(self) -> None:
        keys = self._keys | (self._window.keys if self._window is not None else 0)
        if keys != self._applied_keys:
            self._applied_keys = keys
            self._core.set_keys(keys)

    def set_emulation_speed(self, target_speed) -> None:
        """Speed limit as a multiple of real time (60 fps). 0 = unlimited.

        Default: 1 with a window, 0 (unlimited) without.
        """
        if not isinstance(target_speed, (int, float)) or target_speed < 0:
            raise PymelonDSInvalidInputException("target_speed must be a number >= 0")
        self._limiter.speed = target_speed

    def _post_handle_events(self) -> None:
        while self._delayed and self._delayed[0][0] <= self.frame_count:
            self._events.append(heapq.heappop(self._delayed)[2])

    # ---- input --------------------------------------------------------------

    @staticmethod
    def _mask(input) -> int:
        mask = BUTTONS.get(input.lower())
        if mask is None:
            raise PymelonDSInvalidInputException(f"Unrecognized input: {input}")
        return mask

    def _send(self, mask: int, pressed: bool, delay: int = 0) -> None:
        if delay < 0:
            raise PymelonDSInvalidInputException("Only positive integers allowed")
        if delay == 0:
            self._events.append((mask, pressed))
        else:
            heapq.heappush(self._delayed, (self.frame_count + delay, next(self._seq), (mask, pressed)))

    def button(self, input: str, delay: int = 1) -> None:
        """Press `input` now and release it `delay` frames later.

        Inputs: a, b, x, y, l, r, start, select, up, down, left, right (case-insensitive).
        """
        mask = self._mask(input)
        try:
            delay = operator.index(delay)
        except TypeError:
            raise PymelonDSInvalidInputException("delay must be an integer") from None
        if delay < 0:
            raise PymelonDSInvalidInputException("Only positive integers allowed")
        self._send(mask, True)
        self._send(mask, False, delay)

    def button_press(self, input: str) -> None:
        """Hold `input` from the next frame until button_release."""
        self._send(self._mask(input), True)

    def button_release(self, input: str) -> None:
        """Release `input` from the next frame."""
        self._send(self._mask(input), False)

    # ---- states -------------------------------------------------------------

    def save_state(self, file_like_object) -> None:
        """Write a savestate to a binary file-like object (open(..., 'wb') or io.BytesIO)."""
        if self.stopped:
            raise PymelonDSInvalidOperationException("Emulator is stopped")
        _check_state_file(file_like_object, "save_state")
        file_like_object.write(self._core.save_state())
        file_like_object.flush()

    def load_state(self, file_like_object) -> None:
        """Load a savestate from a binary file-like object (reads from its current position)."""
        if self.stopped:
            raise PymelonDSInvalidOperationException("Emulator is stopped")
        _check_state_file(file_like_object, "load_state")
        self._core.load_state(file_like_object.read())
        self._core.set_keys(self._applied_keys)

    # ---- lifecycle ----------------------------------------------------------

    def stop(self, save=True, sav_file=None) -> None:
        """Stop the emulator. With save=True the battery save is written to sav_file (default: self.sav_file).
        Nothing is written if there is no save path (ROM given as a file object without sav_file)."""
        if self.stopped:
            return
        try:
            target = sav_file if sav_file is not None else self.sav_file
            if save and target is not None:
                self._core.write_save(target)
        finally:
            if self._window is not None:
                self._window.close()
                self._window = None
            self._core.close()
            self.stopped = True

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def __del__(self):
        if getattr(self, "stopped", True) is False:
            self.stop(save=False)
