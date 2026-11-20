"""Optional SDL2 window: shows both screens, keyboard input, mouse = stylus.

Needs `pip install pysdl2 pysdl2-dll`. Only imported when a window is requested.
"""

import ctypes
import time

from . import _bindings as _b
from .exceptions import PymelonDSDependencyError

# DS button -> SDL keycode name (melonDS desktop defaults)
DEFAULT_KEYMAP = {
    "a": "x",
    "b": "z",
    "x": "s",
    "y": "a",
    "l": "q",
    "r": "w",
    "start": "return",
    "select": "backspace",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}

FPS = 59.8261  # DS refresh rate


def _import_sdl2():
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import sdl2
    except ImportError as e:
        raise PymelonDSDependencyError(
            'window="SDL2" needs PySDL2: pip install pysdl2 pysdl2-dll'
        ) from e
    return sdl2


class SDL2Window:
    def __init__(self, scale: int, title: str, buttons: dict):
        sdl2 = self.sdl2 = _import_sdl2()
        self.scale = scale
        w, h = _b.SCREEN_WIDTH, _b.SCREEN_HEIGHT * 2

        if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_VIDEO) != 0:
            raise PymelonDSDependencyError("SDL2 init failed: " + sdl2.SDL_GetError().decode())
        sdl2.SDL_SetHint(sdl2.SDL_HINT_RENDER_SCALE_QUALITY, b"0")  # nearest neighbour

        self.window = sdl2.SDL_CreateWindow(
            title.encode(),
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            w * scale,
            h * scale,
            sdl2.SDL_WINDOW_SHOWN | sdl2.SDL_WINDOW_RESIZABLE | sdl2.SDL_WINDOW_ALLOW_HIGHDPI,
        )
        if not self.window:
            raise PymelonDSDependencyError("SDL2 window failed: " + sdl2.SDL_GetError().decode())
        self.renderer = sdl2.SDL_CreateRenderer(self.window, -1, 0)
        sdl2.SDL_RenderSetLogicalSize(self.renderer, w, h)
        self.texture = sdl2.SDL_CreateTexture(
            self.renderer, sdl2.SDL_PIXELFORMAT_RGBA32, sdl2.SDL_TEXTUREACCESS_STREAMING, w, h
        )

        self._buf = bytearray(_b.SCREEN_BYTES * 2)
        mv = memoryview(self._buf)
        self._top, self._bottom = mv[: _b.SCREEN_BYTES], mv[_b.SCREEN_BYTES :]
        self._ptr = ctypes.c_void_p(ctypes.addressof(ctypes.c_char.from_buffer(self._buf)))

        self._keymap = {sdl2.SDL_GetKeyFromName(k.encode()): buttons[name] for name, k in DEFAULT_KEYMAP.items()}
        self._esc = sdl2.SDLK_ESCAPE
        self.keys = 0
        self.quit = False
        self._touching = False
        self._event = sdl2.SDL_Event()

    # ---- input --------------------------------------------------------------

    def _touch_pos(self, wx, wy):
        """Window coordinates -> bottom-screen coordinates, or None if outside the bottom screen."""
        sdl2 = self.sdl2
        lx, ly = ctypes.c_float(), ctypes.c_float()
        sdl2.SDL_RenderWindowToLogical(self.renderer, wx, wy, ctypes.byref(lx), ctypes.byref(ly))
        x, y = int(lx.value), int(ly.value) - _b.SCREEN_HEIGHT
        if 0 <= x < _b.SCREEN_WIDTH and 0 <= y < _b.SCREEN_HEIGHT:
            return x, y
        return None

    def poll(self, core) -> None:
        sdl2, ev = self.sdl2, self._event
        while sdl2.SDL_PollEvent(ctypes.byref(ev)):
            t = ev.type
            if t == sdl2.SDL_QUIT:
                self.quit = True
            elif t in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
                sym = ev.key.keysym.sym
                if sym == self._esc and t == sdl2.SDL_KEYDOWN:
                    self.quit = True
                elif sym in self._keymap and not ev.key.repeat:
                    if t == sdl2.SDL_KEYDOWN:
                        self.keys |= self._keymap[sym]
                    else:
                        self.keys &= ~self._keymap[sym]
            elif t == sdl2.SDL_MOUSEBUTTONDOWN and ev.button.button == sdl2.SDL_BUTTON_LEFT:
                pos = self._touch_pos(ev.button.x, ev.button.y)
                if pos:
                    core.touch(*pos)
                    self._touching = True
            elif t == sdl2.SDL_MOUSEMOTION and self._touching:
                pos = self._touch_pos(ev.motion.x, ev.motion.y)
                if pos:
                    core.touch(*pos)
                else:
                    core.release_touch()
                    self._touching = False
            elif t == sdl2.SDL_MOUSEBUTTONUP and ev.button.button == sdl2.SDL_BUTTON_LEFT and self._touching:
                core.release_touch()
                self._touching = False
            elif t == sdl2.SDL_WINDOWEVENT and ev.window.event == sdl2.SDL_WINDOWEVENT_FOCUS_LOST:
                self.keys = 0  # don't leave buttons stuck when the window loses focus

    # ---- output -------------------------------------------------------------

    def present(self, core) -> None:
        sdl2 = self.sdl2
        core.screens_into(self._top, self._bottom)
        sdl2.SDL_UpdateTexture(self.texture, None, self._ptr, _b.SCREEN_WIDTH * 4)
        sdl2.SDL_RenderClear(self.renderer)
        sdl2.SDL_RenderCopy(self.renderer, self.texture, None, None)
        sdl2.SDL_RenderPresent(self.renderer)

    def close(self) -> None:
        sdl2 = self.sdl2
        if self.window:
            sdl2.SDL_DestroyTexture(self.texture)
            sdl2.SDL_DestroyRenderer(self.renderer)
            sdl2.SDL_DestroyWindow(self.window)
            self.window = None
            sdl2.SDL_QuitSubSystem(sdl2.SDL_INIT_VIDEO)


class FrameLimiter:
    """Sleeps so frames run at `speed` x real time (0 = unlimited)."""

    def __init__(self, speed: float):
        self.speed = speed
        self._next = None

    def wait(self) -> None:
        if self.speed <= 0:
            self._next = None
            return
        period = 1.0 / (FPS * self.speed)
        now = time.perf_counter()
        if self._next is None or now - self._next > 0.25:  # first frame, or far behind: resync
            self._next = now
        self._next += period
        delay = self._next - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
