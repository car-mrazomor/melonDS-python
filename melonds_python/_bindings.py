"""Low-level ctypes bindings for libmelonds_py (native/melonds_shim.h).

Mirrors the C API 1:1. The user-facing API is built on top of this.
"""

import ctypes
import sys
from ctypes import POINTER, c_char_p, c_int, c_uint8, c_int16, c_uint16, c_uint32, c_uint64, c_void_p
from pathlib import Path

from .exceptions import PymelonDSException

SCREEN_WIDTH = 256
SCREEN_HEIGHT = 192
SCREEN_BYTES = SCREEN_WIDTH * SCREEN_HEIGHT * 4  # RGBA8888

KEY_A = 1 << 0
KEY_B = 1 << 1
KEY_SELECT = 1 << 2
KEY_START = 1 << 3
KEY_RIGHT = 1 << 4
KEY_LEFT = 1 << 5
KEY_UP = 1 << 6
KEY_DOWN = 1 << 7
KEY_R = 1 << 8
KEY_L = 1 << 9
KEY_X = 1 << 10
KEY_Y = 1 << 11


def _lib_path() -> Path:
    if sys.platform == "darwin":
        names = ["libmelonds_py.dylib"]
    elif sys.platform == "win32":
        names = ["libmelonds_py.dll", "melonds_py.dll"]  # MinGW / MSVC naming
    else:
        names = ["libmelonds_py.so"]
    libdir = Path(__file__).parent / "_lib"
    for name in names:
        if (libdir / name).exists():
            return libdir / name
    raise OSError(f"melonDS native library not found in {libdir}; build it first (see README)")


class MelonDSError(PymelonDSException):
    """Error reported by the native melonDS library."""


lib = ctypes.CDLL(str(_lib_path()))

_mds_p = c_void_p

_SIGNATURES = {
    "mds_last_error": (c_char_p, []),
    "mds_set_log_level": (None, [c_int]),
    "mds_create": (_mds_p, [c_char_p, c_char_p, c_char_p, c_int]),
    "mds_destroy": (None, [_mds_p]),
    "mds_load_rom": (c_int, [_mds_p, c_char_p, c_char_p]),
    "mds_load_rom_mem": (c_int, [_mds_p, c_char_p, c_uint32, c_char_p]),
    "mds_write_save": (c_int, [_mds_p, c_char_p]),
    "mds_reset": (c_int, [_mds_p]),
    "mds_run_frame": (c_uint32, [_mds_p]),
    "mds_frame_count": (c_uint64, [_mds_p]),
    "mds_set_keys": (None, [_mds_p, c_uint32]),
    "mds_get_keys": (c_uint32, [_mds_p]),
    "mds_touch": (None, [_mds_p, c_int, c_int]),
    "mds_release_touch": (None, [_mds_p]),
    "mds_set_lid_closed": (None, [_mds_p, c_int]),
    "mds_get_screens": (c_int, [_mds_p, c_void_p, c_void_p]),
    "mds_audio_available": (c_int, [_mds_p]),
    "mds_read_audio": (c_int, [_mds_p, POINTER(c_int16), c_int]),
    "mds_save_state": (c_int, [_mds_p, POINTER(POINTER(c_uint8)), POINTER(c_uint32)]),
    "mds_load_state": (c_int, [_mds_p, c_char_p, c_uint32]),
    "mds_free": (None, [c_void_p]),
    "mds_read8": (c_uint8, [_mds_p, c_uint32]),
    "mds_read16": (c_uint16, [_mds_p, c_uint32]),
    "mds_read32": (c_uint32, [_mds_p, c_uint32]),
    "mds_write8": (None, [_mds_p, c_uint32, c_uint8]),
    "mds_write16": (None, [_mds_p, c_uint32, c_uint16]),
    "mds_write32": (None, [_mds_p, c_uint32, c_uint32]),
    "mds_main_ram": (c_uint32, [_mds_p, POINTER(POINTER(c_uint8))]),
}

for _name, (_res, _args) in _SIGNATURES.items():
    _fn = getattr(lib, _name)
    _fn.restype = _res
    _fn.argtypes = _args


def last_error() -> str:
    return (lib.mds_last_error() or b"").decode("utf-8", "replace")


def check(rc: int) -> None:
    if rc != 0:
        raise MelonDSError(last_error() or "unknown melonDS error")


def _enc(path) -> bytes | None:
    return None if path is None else str(path).encode()


class Core:
    """Owns one native emulator instance. Thin, 1:1 wrapper over the C API."""

    def __init__(self, bios9=None, bios7=None, firmware=None, jit: bool = True):
        self._h = lib.mds_create(_enc(bios9), _enc(bios7), _enc(firmware), int(jit))
        if not self._h:
            raise MelonDSError(last_error() or "mds_create failed")
        self._top = (c_uint8 * SCREEN_BYTES)()
        self._bottom = (c_uint8 * SCREEN_BYTES)()

    def close(self) -> None:
        if self._h:
            lib.mds_destroy(self._h)
            self._h = None

    def __del__(self):
        self.close()

    def load_rom(self, rom, sav=None) -> None:
        check(lib.mds_load_rom(self._h, _enc(rom), _enc(sav)))

    def load_rom_bytes(self, data: bytes, sav=None) -> None:
        check(lib.mds_load_rom_mem(self._h, bytes(data), len(data), _enc(sav)))

    def write_save(self, sav) -> None:
        """Write the cartridge's battery save memory to a file."""
        check(lib.mds_write_save(self._h, _enc(sav)))

    def reset(self) -> None:
        check(lib.mds_reset(self._h))

    def run_frame(self) -> int:
        return lib.mds_run_frame(self._h)

    def frame_count(self) -> int:
        return lib.mds_frame_count(self._h)

    def set_keys(self, mask: int) -> None:
        lib.mds_set_keys(self._h, mask)

    def get_keys(self) -> int:
        return lib.mds_get_keys(self._h)

    def touch(self, x: int, y: int) -> None:
        lib.mds_touch(self._h, x, y)

    def release_touch(self) -> None:
        lib.mds_release_touch(self._h)

    def set_lid_closed(self, closed: bool) -> None:
        lib.mds_set_lid_closed(self._h, int(closed))

    def screens_into(self, top, bottom) -> None:
        """Copy the last frame (RGBA) into writable buffers of SCREEN_BYTES each (either may be None)."""
        def ptr(buf):
            if buf is None:
                return None
            return ctypes.addressof(ctypes.c_char.from_buffer(buf))
        check(lib.mds_get_screens(self._h, ptr(top), ptr(bottom)))

    def screens(self) -> tuple[bytes, bytes]:
        """(top, bottom) as raw RGBA bytes, 256x192 each."""
        check(lib.mds_get_screens(self._h, self._top, self._bottom))
        return bytes(self._top), bytes(self._bottom)

    def audio_available(self) -> int:
        return lib.mds_audio_available(self._h)

    def read_audio(self, max_frames: int = 4096) -> bytes:
        """Interleaved stereo s16 @ 48 kHz as raw bytes."""
        buf = (c_int16 * (max_frames * 2))()
        n = lib.mds_read_audio(self._h, buf, max_frames)
        return bytes(buf)[: n * 4]

    def save_state(self) -> bytes:
        ptr = POINTER(c_uint8)()
        size = c_uint32()
        check(lib.mds_save_state(self._h, ctypes.byref(ptr), ctypes.byref(size)))
        try:
            return ctypes.string_at(ptr, size.value)
        finally:
            lib.mds_free(ptr)

    def load_state(self, data: bytes) -> None:
        check(lib.mds_load_state(self._h, data, len(data)))

    def read8(self, addr: int) -> int:
        return lib.mds_read8(self._h, addr)

    def read16(self, addr: int) -> int:
        return lib.mds_read16(self._h, addr)

    def read32(self, addr: int) -> int:
        return lib.mds_read32(self._h, addr)

    def write8(self, addr: int, val: int) -> None:
        lib.mds_write8(self._h, addr, val)

    def write16(self, addr: int, val: int) -> None:
        lib.mds_write16(self._h, addr, val)

    def write32(self, addr: int, val: int) -> None:
        lib.mds_write32(self._h, addr, val)

    def main_ram(self) -> memoryview:
        """Live, writable view of main RAM (valid while the Core is alive)."""
        ptr = POINTER(c_uint8)()
        size = lib.mds_main_ram(self._h, ctypes.byref(ptr))
        return memoryview((c_uint8 * size).from_address(ctypes.addressof(ptr.contents))).cast("B")


def set_log_level(level: int) -> None:
    """0 debug, 1 info, 2 warn (default), 3 error, 4 silent."""
    lib.mds_set_log_level(level)
