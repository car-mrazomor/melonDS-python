# melonDS-python

Python bindings for the [melonDS](https://melonds.kuribo64.net) Nintendo DS emulator.
Headless by default: run frames, press buttons, grab both screens, save/load states. Optional SDL2 window to watch or play.
Built for driving DS games from scripts and AI agents, with an API modelled on [PyBoy](https://github.com/Baekalfen/PyBoy).

How it works: the melonDS core is compiled (without its Qt UI) into a small shared library with a C API
(`native/melonds_shim.h`), which Python loads with `ctypes`. No BIOS or firmware dumps needed;
it uses melonDS's built-in FreeBIOS and a generated firmware by default.

**Documentation:** [docs/](docs/README.md): getting started, API reference, input timing, screens, window,
states and saves, AI agent usage, PyBoy differences, low-level/C API, internals, troubleshooting.

## Platform support

| OS | Arch | Status |
|---|---|---|
| macOS | Apple Silicon (arm64) | tested |
| macOS | Intel (x86_64) | should work, untested |
| Linux (Ubuntu 24.04) | x86_64 / arm64 | tested |
| Windows 10/11 | x86_64 (MSYS2 / MinGW) | should work, untested |

The JIT recompiler is available on x86_64 and arm64. On other CPUs pass `jit=False`
(the interpreter is roughly 2x slower but still well above real-time).

## Requirements

- C/C++17 compiler (Clang, GCC or MinGW-w64)
- CMake ≥ 3.16
- Ninja (recommended) or Make
- Python ≥ 3.10
- Pillow (`pip install pillow`)
- Optional, for the window: PySDL2 (`pip install pysdl2 pysdl2-dll`)

## Get the source

```sh
git clone https://github.com/car-mrazomor/melonDS-python
cd melonDS-python
```

The melonDS source is included in `melonDS/`, unmodified, from
[melonDS-emu/melonDS](https://github.com/melonDS-emu/melonDS) at commit
[`361ffa95`](https://github.com/melonDS-emu/melonDS/commit/361ffa9501b631d53d7150fe57dec40a8341f664) (1.1+).

## Build

The build produces `melonds_python/_lib/libmelonds_py.{dylib,so,dll}`.

### macOS

```sh
xcode-select --install          # compiler, if you don't have it
brew install cmake ninja
cmake -S . -B build -G Ninja
cmake --build build
```

### Linux

Debian / Ubuntu:

```sh
sudo apt install build-essential cmake ninja-build python3
cmake -S . -B build -G Ninja
cmake --build build
```

Fedora: `sudo dnf install gcc-c++ cmake ninja-build python3`. Arch: `sudo pacman -S base-devel cmake ninja python`.
Then the same two `cmake` commands.

### Windows

Use [MSYS2](https://www.msys2.org) (MSVC is not supported by melonDS). In the **MSYS2 UCRT64** shell:

```sh
pacman -S mingw-w64-ucrt-x86_64-toolchain mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja git
cmake -S . -B build -G Ninja
cmake --build build
```

The DLL is linked statically against the MinGW runtime, so it loads from any regular
Windows Python (python.org, uv, ...), not only the MSYS2 one.

## Quick check

```sh
pip install pillow
python scripts/smoke.py path/to/game.nds            # JIT
python scripts/smoke.py path/to/game.nds --no-jit   # interpreter
```

It prints the speed, writes screenshots (both screens stacked) to `smoke_out/`,
and tests savestates.

## Usage

The API follows [PyBoy](https://docs.pyboy.dk/)'s.

```python
from melonds_python import PymelonDS

pm = PymelonDS("game.nds")          # loads game.sav if it exists
pm.tick()                           # run 1 frame (60 fps)
pm.tick(60, render=False)           # run 60 frames, don't update the screen
pm.frame_count                      # frames run so far

pm.button("a")                      # press A now, release it 1 frame later
pm.button("start", 10)              # hold Start for 10 frames
pm.button_press("left")             # hold until released
pm.tick(30)
pm.button_release("left")

pm.screen.image                     # PIL Image, both screens stacked: 256x384 RGBA
pm.screen.top.image                 # top screen: 256x192 RGBA
pm.screen.bottom.image              # bottom screen: 256x192 RGBA
pm.screen.top.image.save("top.png")

with open("state.bin", "wb") as f:
    pm.save_state(f)
with open("state.bin", "rb") as f:
    pm.load_state(f)

pm.stop()                           # writes the battery save (game.sav)
```

The ROM can also be a file object:

```python
with open("game.nds", "rb") as f:
    pm = PymelonDS(f, sav_file="game.sav")   # without sav_file there is no battery save
```

Watch it in a window (optional, `pip install pysdl2 pysdl2-dll`). Keyboard: X/Z/S/A = A/B/X/Y, Q/W = L/R,
Enter = Start, Backspace = Select, arrows = D-pad. The mouse on the bottom screen acts as the stylus:

```python
pm = PymelonDS("game.nds", window="SDL2")   # real-time speed; pm.set_emulation_speed(0) for unlimited
while pm.tick():                             # False once the window is closed
    pass
pm.stop()
```

Or as a context manager (`stop()` is called on exit):

```python
with PymelonDS("game.nds") as pm:
    pm.tick(600)
```

### Constructor

```python
PymelonDS(gamerom, *, sav_file=None, bios9=None, bios7=None, firmware=None, jit=True,
          window="null", scale=2)
```

| Argument | Default | Meaning |
|---|---|---|
| `gamerom` | | path to the `.nds` ROM, or a binary file-like object (`open(..., "rb")`, `io.BytesIO`) |
| `sav_file` | ROM path with `.sav` (`None` for a file object) | battery save, loaded at start (if it exists) and written by `stop()`. If it's `None`, no battery save is used. |
| `bios9`, `bios7`, `firmware` | `None` | your own dumps; FreeBIOS and a generated firmware are used otherwise |
| `jit` | `True` | JIT recompiler (about 2x faster than the interpreter) |
| `window` | `"null"` | `"null"` = no window, `"SDL2"` = window (needs `pip install pysdl2 pysdl2-dll`) |
| `scale` | `2` | window size multiplier |

### Methods and attributes

| | |
|---|---|
| `tick(count=1, render=True) -> bool` | Run `count` frames. If `render` is True, the screen is updated after the last frame. Returns `False` once the window was closed, otherwise `True`. |
| `set_emulation_speed(n)` | Speed limit, n × real time. `0` = unlimited (the default without a window). With a window the default is `1`. |
| `button(input, delay=1)` | Press now and release `delay` frames later. |
| `button_press(input)` | Press from the next frame until `button_release`. |
| `button_release(input)` | Release from the next frame. |
| `screen.image`, `screen.top.image`, `screen.bottom.image` | PIL images (RGBA). |
| `screen.raw_buffer`, `.raw_buffer_dims`, `.raw_buffer_format` | The same pixels as a `memoryview`, `(height, width)`, `"RGBA"`. Also on `.top` and `.bottom`. |
| `save_state(f)` / `load_state(f)` | Binary file-like object (`open(..., "wb"/"rb")` or `io.BytesIO`). A path or a text-mode file raises an error. `load_state` reads from the current position, so call `seek(0)` on a `BytesIO` first. |
| `stop(save=True, sav_file=None)` | Stop the emulator. With `save=True` the battery save is written. Calling it again does nothing. |
| `frame_count` | Frames run since start. |

**Buttons** (case-insensitive): `a` `b` `x` `y` `l` `r` `start` `select` `up` `down` `left` `right`.

Presses and releases take effect at the start of the next frame, like PyBoy. So `pm.button("a")` followed by
`pm.tick()` holds A during that frame.

**Screens are live.** As in PyBoy, the image objects show the latest frame after every rendered `tick`.
Use `.copy()` to keep a frame:

```python
frames = []
for _ in range(10):
    pm.tick(30)
    frames.append(pm.screen.image.copy())
```

**Errors:** `PymelonDSInvalidInputException` for an unknown button, a negative or non-integer `count`/`delay`,
a path or text-mode file passed to `save_state`/`load_state`, or a text-mode or empty `gamerom` object. A file that isn't a valid DS ROM raises `PymelonDSException`. `PymelonDSInvalidOperationException` when
calling `tick`, `save_state` or `load_state` after `stop()`. `FileNotFoundError` for a missing ROM or BIOS file.
`PymelonDSDependencyError` when `window="SDL2"` is used without PySDL2.
All of them except `FileNotFoundError` inherit from `PymelonDSException`.

### Low-level

`melonds_python._bindings.Core` maps 1:1 to the C API in `native/melonds_shim.h`. It also has things the
PyBoy-style API doesn't expose: touch, memory read/write, audio.

```python
from melonds_python import _bindings as mds

core = mds.Core()                       # Core(bios9=..., bios7=..., firmware=..., jit=True)
core.load_rom("game.nds", "game.sav")   # .sav is optional and only loaded
core.load_rom_bytes(rom_bytes, None)    # ROM from memory
core.set_keys(mds.KEY_A | mds.KEY_UP)   # held until changed; 0 releases everything
core.run_frame()
core.touch(128, 96)                     # bottom screen, x 0-255, y 0-191
core.release_touch()
top, bottom = core.screens()            # raw RGBA bytes, 256x192 each
state = core.save_state()               # bytes
core.load_state(state)
core.write_save("game.sav")             # write the battery save
ram = core.main_ram()                   # live memoryview of the 4 MB main RAM
value = core.read32(0x02000000)         # ARM9 bus read
mds.set_log_level(0)                    # 0 debug ... 4 silent (default 2, warn)
```

### BIOS / firmware (optional)

Some games are picky about FreeBIOS. If you have dumps from your own console:

```python
pm = PymelonDS("game.nds", bios9="bios9.bin", bios7="bios7.bin", firmware="firmware.bin")
```

## Notes

- DS only. DSi mode, GBA slot, Wi-Fi, local multiplayer, mic and camera are not exposed. No sound output.
- Only the software renderer (native 256x192).
- Bring your own ROMs. Don't commit them (`.gitignore` already excludes `*.nds`, `*.sav`, `*.bin`).

## License

GPL-3.0, same as melonDS (this project links its core).
