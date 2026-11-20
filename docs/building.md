# Building

The Python package loads a native library built from the melonDS core plus a small C shim.
You build it once per machine (and again after changing anything in `native/` or `melonDS/`).

## Requirements

| | |
|---|---|
| Compiler | C++17: Clang, GCC or MinGW-w64 |
| CMake | ≥ 3.16 |
| Generator | Ninja (recommended) or Make |
| Python | ≥ 3.10 |
| Python packages | Pillow |

No Qt, SDL, OpenGL or other libraries are needed.

## Platform support

| OS | Arch | Status |
|---|---|---|
| macOS | Apple Silicon (arm64) | tested |
| macOS | Intel (x86_64) | should work, untested |
| Linux (Ubuntu 24.04) | x86_64 / arm64 | tested |
| Windows 10/11 | x86_64 (MSYS2 / MinGW) | should work, untested |

## macOS

```sh
xcode-select --install          # compiler, if you don't have it
brew install cmake ninja
cmake -S . -B build -G Ninja
cmake --build build
```

Output: `melonds_python/_lib/libmelonds_py.dylib`

## Linux

Debian / Ubuntu:

```sh
sudo apt install build-essential cmake ninja-build python3
cmake -S . -B build -G Ninja
cmake --build build
```

Fedora:

```sh
sudo dnf install gcc-c++ cmake ninja-build python3
```

Arch:

```sh
sudo pacman -S base-devel cmake ninja python
```

Then run the same two `cmake` commands. Output: `melonds_python/_lib/libmelonds_py.so`

## Windows

melonDS doesn't build with MSVC, so use [MSYS2](https://www.msys2.org). In the **MSYS2 UCRT64** shell:

```sh
pacman -S mingw-w64-ucrt-x86_64-toolchain mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja git
cmake -S . -B build -G Ninja
cmake --build build
```

Output: `melonds_python/_lib/libmelonds_py.dll`. It's linked statically against the MinGW runtime
(`-static-libgcc -static-libstdc++ -static`), so a regular Windows Python (python.org, uv, ...)
can load it without any MSYS2 DLLs.

## Without Ninja

```sh
cmake -S . -B build
cmake --build build -j
```

## Rebuilding

| Change | What to run |
|---|---|
| Edited `native/*.cpp` or `native/*.h` | `cmake --build build` |
| Edited `CMakeLists.txt` | `cmake --build build` (CMake reconfigures itself) |
| Updated `melonDS/` | `cmake --build build` |
| Odd build errors, switched compiler | `rm -rf build` and configure again |
| Edited Python files only | nothing |

## What the build does

`CMakeLists.txt` at the repo root:

1. Adds `melonDS/` as a subproject with these options forced:

   | Option | Value | Why |
   |---|---|---|
   | `BUILD_QT_SDL` | `OFF` | no desktop UI |
   | `ENABLE_OGLRENDERER` | `OFF` | software renderer only, no OpenGL |
   | `ENABLE_GDBSTUB` | `OFF` | not needed |
   | `ENABLE_LTO_RELEASE` | `OFF` | faster, simpler builds |

   The JIT (`ENABLE_JIT`) stays on wherever melonDS supports it (x86_64 and arm64).
2. Builds melonDS's static `core` library with position-independent code.
3. Builds the shared library `melonds_py` from `native/melonds_shim.cpp` and `native/Platform.cpp`, linked to `core`.
   Only the `mds_*` functions are exported (`-fvisibility=hidden`).
4. Writes it to `melonds_python/_lib/`.

The default build type is `Release`. For a debug build:

```sh
cmake -S . -B build-debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build-debug
```

Note that `build-debug` writes to the same `melonds_python/_lib/` folder, replacing the release library.

## Checking the build

```sh
python scripts/smoke.py path/to/game.nds            # with JIT
python scripts/smoke.py path/to/game.nds --no-jit   # interpreter
```

Build problems are covered in [Troubleshooting](troubleshooting.md#build).
