# How it works

## Layout

```text
melonDS-python/
├── CMakeLists.txt              builds melonDS core + shim into one shared library
├── melonDS/                    melonDS source, unmodified (commit 361ffa95)
├── native/
│   ├── melonds_shim.h          C API (mds_*)
│   ├── melonds_shim.cpp        C API implementation on top of melonDS's NDS class
│   └── Platform.cpp            headless implementation of melonDS's Platform interface
├── melonds_python/
│   ├── __init__.py             public exports
│   ├── pymelonds.py            PymelonDS (PyBoy-style API)
│   ├── exceptions.py           exception classes
│   ├── _bindings.py            ctypes bindings + Core class
│   ├── window.py               optional SDL2 window + frame limiter
│   └── _lib/                   built library (not in git)
├── scripts/smoke.py            quick end-to-end check
└── docs/
```

## Layers

### 1. melonDS core

melonDS is split into a **core** (`melonDS/src/*.cpp`: CPUs, GPU, sound, cartridge, ...) and a **frontend**
(`melonDS/src/frontend/qt_sdl`: the desktop app). Only the core is built, as a static library. It's compiled
without OpenGL and without the GDB stub. The software renderer is used, which needs nothing from the system.

The core asks its frontend for system services (files, threads, logging, saving) through functions declared in
`melonDS/src/Platform.h`. A frontend has to implement them.

### 2. `native/Platform.cpp`

A minimal, headless frontend:

| Service | Implementation |
|---|---|
| Files | `fopen`/`fread`/... |
| Threads, semaphores, mutexes | `std::thread`, `std::mutex`, `std::condition_variable` |
| Time / sleep | `std::chrono` |
| Logging | stderr, filtered by `mds_set_log_level` |
| Battery save written by the game | ignored here; saved explicitly by `mds_write_save` |
| Firmware / RTC written by the game | ignored |
| Wi-Fi, local multiplayer, network | stubs (no connection) |
| Microphone, camera | stubs (silence, black) |
| Rumble / guitar grip / motion pak | stubs |
| AAC decoder (DSi only) | not available |
| Dynamic libraries | `dlopen` (unused in practice) |

### 3. `native/melonds_shim.cpp`

A C API over `melonDS::NDS`, so any FFI can use it:

- **`mds_create`** builds `NDSArgs`: BIOS images (FreeBIOS by default), firmware (a generated one by default) and
  JIT settings. Then it constructs `NDS`.
- **`mds_load_rom`** reads the ROM (and `.sav`), calls `NDSCart::ParseROM` and `SetNDSCart`, then boots:
  `Reset()`, `SetupDirectBoot()` if the BIOS/firmware can't boot a game by themselves, then `Start()`.
- **`mds_run_frame`** calls `NDS::RunFrame()`.
- **Input:** melonDS's key register uses `0` = pressed. The shim takes `1` = pressed and inverts it.
- **Video:** the software renderer keeps two framebuffers per screen in `0xAARRGGBB` format. `mds_get_screens`
  copies the front buffer and converts to RGBA bytes.
- **Savestates** use melonDS's `Savestate` class in memory. `mds_save_state` hands back a `malloc`'d copy.
- **Errors** are stored in a thread-local string returned by `mds_last_error`.
- **Apple Silicon JIT:** JIT memory is either writable or executable, per thread. melonDS's JIT destructor leaves the
  thread in "writable" mode, which would crash any other JIT instance on that thread. `mds_run_frame` and
  `mds_destroy` put the thread back in "executable" mode (`pthread_jit_write_protect_np(1)`), so the vendored
  melonDS stays unmodified.
- Only `mds_*` symbols are exported. Everything else is hidden.

### 4. `_bindings.py`

Loads `_lib/libmelonds_py.{dylib,so,dll}` with `ctypes.CDLL`, declares argument and return types for every
`mds_*` function, and wraps them in the `Core` class. Non-zero return codes become `MelonDSError`.

### 5. `window.py` (optional)

Only imported for `window="SDL2"`. It uses PySDL2 to create a window, a renderer and a streaming RGBA texture
(384×256, scaled with nearest-neighbour). Every frame it copies both screens into its own buffer and uploads them.
Keyboard events become a key mask that `tick()` ORs with the API's keys. Mouse events on the bottom half call
`Core.touch` / `release_touch`. `FrameLimiter` sleeps to hold `speed × 59.8261` fps.

### 6. `pymelonds.py`

The PyBoy-style layer, in pure Python:

- **Input queue:** `button*` calls add `(mask, pressed)` events. Delayed releases go into a heap keyed by frame number.
  `tick()` applies pending events before each frame and moves due delayed events into the queue after it.
- **Screen:** one 384×256×4 `bytearray`. `top` and `bottom` are `memoryview` slices of it. The PIL images are
  created with `Image.frombuffer` over those views, so they change in place. After a rendered tick the shim
  copies both screens straight into the two halves.
- **States:** pass-through to `Core.save_state` / `load_state`, plus PyBoy's argument checks.
- **Battery save:** the `.sav` path is passed to `load_rom` at start and written with `write_save` in `stop()`.

## Emulated machine

- Console: Nintendo DS (not DSi).
- BIOS: FreeBIOS (melonDS's open replacement) unless dumps are given.
- Firmware: generated by melonDS unless a dump is given. User name "melonDS", language English.
- Real-time clock: starts at **2000-01-01 00:00:00** on every boot and runs with emulated time (not wall-clock time).
  Games that use the clock (day/night, events) always start at midnight on 1 January 2000.
- Determinism: same ROM, same `.sav`, same inputs on the same frames → same frames. That holds with the JIT and
  with the interpreter.

## Why ctypes

Using ctypes means no Python headers or build step on the Python side: one shared library works with any
Python ≥ 3.10 version and interpreter build. The C API is small (about 30 functions) and all calls are cheap
compared with emulating a frame, so ctypes overhead doesn't matter.
