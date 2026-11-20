# Troubleshooting

## Build

**`cmake: command not found`**
Install CMake: `brew install cmake` (macOS), `sudo apt install cmake` (Debian/Ubuntu),
`pacman -S mingw-w64-ucrt-x86_64-cmake` (MSYS2).

**`CMake Error: ... Ninja`**
Install Ninja, or leave out `-G Ninja` to use Make: `cmake -S . -B build && cmake --build build -j`.

**CMake warnings about `CMP0218` or deprecated policies**
They come from melonDS's bundled `teakra` library and are harmless.

**Errors after switching compilers or moving the folder**
Delete the build folder and configure again: `rm -rf build && cmake -S . -B build -G Ninja && cmake --build build`.

**Windows: MSVC errors**
melonDS doesn't support MSVC. Use the MSYS2 UCRT64 shell ([Building](building.md#windows)).

## Import / loading

**`OSError: melonDS native library not found in .../melonds_python/_lib; build it first`**
The native library isn't built, or was built somewhere else. Run the build ([Building](building.md)). The output must
be in `melonds_python/_lib/`.

**`OSError: ... incompatible architecture` (macOS) / `wrong ELF class` (Linux)**
Python and the library are built for different CPU architectures, for example an x86_64 Python under
Rosetta with an arm64 library. Use a Python for the same architecture, or rebuild the library with that Python's
architecture (`-DCMAKE_OSX_ARCHITECTURES=x86_64` on macOS).

**`ModuleNotFoundError: No module named 'melonds_python'`**
Run from the repository root, or add it to `PYTHONPATH`: `export PYTHONPATH=/path/to/melonDS-python`.

**`ModuleNotFoundError: No module named 'PIL'`**
`pip install pillow`.

**macOS: the package ended up inside `melonDS/`**
The macOS filesystem treats `melonds` and `melonDS` as the same name. That's why the Python package is called
`melonds_python`. Don't rename it to `melonds`.

## Running

**`PymelonDSException: failed to parse ROM`**
The file isn't a valid `.nds` ROM (or it's truncated, compressed or a DSi-only title). Check the file. For zipped
ROMs, unzip first.

**`PymelonDSInvalidInputException: gamerom file object must be opened in binary mode`**
Use `open(path, "rb")`, not `"r"`.

**`save_state takes a file-like object, not a path`**
Use `with open("x.state", "wb") as f: pm.save_state(f)`.

**`load_state` fails right after `save_state` into a `BytesIO`**
The position is at the end. Call `buf.seek(0)` before `load_state(buf)`.

**`PymelonDSInvalidOperationException: Emulator is stopped`**
`stop()` was called, or a `with` block ended. Create a new `PymelonDS`.

**The screen is black**
- Before the first `tick()` it is always black. Games also take a few seconds to boot: try `pm.tick(600)`.
- After `tick(..., render=False)` or `load_state`, the screen isn't updated. Call `pm.tick()`.

**My saved images all look the same / show the latest frame**
`pm.screen.image` is live. Store `pm.screen.image.copy()` ([Screens](screen.md#live-images-copy-what-you-keep)).

**Button presses are ignored**
- Press and release without a `tick()` in between cancel out. `button(x, 0)` does nothing.
- The game may need a longer hold (`button("a", 4)`) or may still be in a transition. Wait more frames.
- See [Input](input.md).

**In-game progress is lost**
The `.sav` is only written by `stop()` (or at the end of a `with` block). A crash or a garbage-collected object
doesn't write it. Also check `pm.sav_file`: with a ROM given as a file object and no `sav_file`, there is no save.

**`PymelonDSDependencyError: window="SDL2" needs PySDL2`**
`pip install pysdl2 pysdl2-dll`.

**The window says "not responding" / doesn't react to keys**
The window only works inside `tick()`. Keep calling `tick()`. On macOS, the window must be created and ticked
from the main thread. See [Window](window.md#things-to-know).

**The window runs at 60 fps but I want it faster**
`pm.set_emulation_speed(0)` for unlimited, or `4` for 4×.

**`this is a JIT bug!` and the process aborts**
Make sure you're on a current build (`cmake --build build`). Older builds crashed on Apple Silicon when one JIT
instance was stopped while another kept running. If it still happens, use `jit=False` and report the game and
the steps.

**A game hangs, crashes or shows glitches**
- Try `jit=False`.
- Try real BIOS and firmware dumps (`bios9=`, `bios7=`, `firmware=`). FreeBIOS isn't perfect.
- Check melonDS's compatibility for that game. The same issue likely happens in desktop melonDS.

**The in-game clock is wrong**
The DS clock always starts at 2000-01-01 00:00 ([How it works](architecture.md#emulated-machine)).

**`savestate: VERY BAD!!!! SRAM LENGTH DIFFERENT` in the output**
The state was made with a different save size (different game or `.sav`). Load states only into the same game.

**Too much log output**
`from melonds_python import _bindings; _bindings.set_log_level(3)` (errors only) or `4` (silent).

## Performance

| | Apple Silicon (JIT) | Apple Silicon (interpreter) |
|---|---|---|
| Frames per second | ~550–900 | ~300 |

Speed depends on the game and scene. If it's much slower:

- make sure you're not on `jit=False`
- use a Release build (the default)
- use `tick(n, render=False)` while waiting. It saves the screen copy, though the emulation itself costs the same.
- don't call `.image.copy()`, `.tobytes()` or PNG encoding every frame unless you need it
