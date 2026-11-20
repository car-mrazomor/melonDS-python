# API reference

```python
from melonds_python import (
    PymelonDS,
    BUTTONS,
    PymelonDSException,
    PymelonDSInvalidInputException,
    PymelonDSInvalidOperationException,
    PymelonDSDependencyError,
)
```

- [PymelonDS](#pymelonds)
  - [Constructor](#constructor)
  - [tick](#tick), [set_emulation_speed](#set_emulation_speed)
  - [button](#button), [button_press](#button_press), [button_release](#button_release)
  - [screen](#screen)
  - [save_state](#save_state), [load_state](#load_state)
  - [stop](#stop), [context manager](#context-manager)
  - [Attributes](#attributes)
- [BUTTONS](#buttons)
- [Exceptions](#exceptions)

---

## PymelonDS

### Constructor

```python
PymelonDS(gamerom, *, sav_file=None, bios9=None, bios7=None, firmware=None, jit=True,
          window="null", scale=2)
```

Creates an emulator, loads the ROM and boots it. Nothing is emulated until the first `tick()`.

| Argument | Type | Default | Meaning |
|---|---|---|---|
| `gamerom` | `str`, `Path` or binary file-like object | required | The `.nds` ROM. A file object (`open(..., "rb")`, `io.BytesIO`, anything with `.read()`) is read once, completely. |
| `sav_file` | `str`, `Path` or `None` | see below | Battery save. Loaded at start if the file exists, written by [`stop()`](#stop). |
| `bios9` | `str`, `Path` or `None` | `None` | ARM9 BIOS dump (4 KiB). `None` uses melonDS's FreeBIOS. |
| `bios7` | `str`, `Path` or `None` | `None` | ARM7 BIOS dump (16 KiB). `None` uses FreeBIOS. |
| `firmware` | `str`, `Path` or `None` | `None` | Firmware dump. `None` uses a generated firmware. |
| `jit` | `bool` | `True` | Use the JIT recompiler. `False` uses the interpreter (about 2× slower). It has no effect on CPUs without JIT support. |
| `window` | `str` | `"null"` | `"null"` (no window; `"headless"`, `"dummy"` are aliases) or `"SDL2"` (needs PySDL2). See [Window](window.md). |
| `scale` | `int` | `2` | Window scale factor (SDL2 only). |

Default `sav_file`:

- if `gamerom` is a path: the same path with the extension replaced by `.sav` (`roms/game.nds` becomes `roms/game.sav`)
- if `gamerom` is a file object: `None`, meaning no battery save is loaded or written

**Boot:** with the defaults (FreeBIOS and/or generated firmware) the game is started with "direct boot": the DS
boot screens are skipped and the game starts at once. With a real BIOS **and** a real bootable firmware dump,
the console boots normally through the DS firmware (health and safety screen, menu), like real hardware.

**Raises**

| Exception | When |
|---|---|
| `FileNotFoundError` | `gamerom` is `None`, or the ROM, BIOS or firmware file doesn't exist |
| `PymelonDSInvalidInputException` | `gamerom` isn't a path or file object, the file object is in text mode, or it's empty; unknown `window`; `scale` < 1 or not an integer |
| `PymelonDSDependencyError` | `window="SDL2"` but PySDL2 isn't installed, or SDL can't open a window |
| `PymelonDSException` | melonDS can't parse the ROM, or a BIOS/firmware file has the wrong size or is invalid |

```python
pm = PymelonDS("roms/pokemon_white.nds")
pm = PymelonDS("game.nds", sav_file="saves/slot1.sav", jit=False)
pm = PymelonDS(io.BytesIO(rom_bytes))
pm = PymelonDS("game.nds", bios9="bios9.bin", bios7="bios7.bin", firmware="firmware.bin")
```

---

### tick

```python
tick(count=1, render=True) -> bool
```

Emulates `count` frames. The DS runs at about 60 frames per second, so `tick(60)` is one second of game time.
Without a window, emulation runs as fast as the CPU allows. With a window it runs at real time by default
(see [set_emulation_speed](#set_emulation_speed)).

- Queued button presses and releases are applied at the **start** of each frame (see [Input](input.md)).
- If `render` is `True`, [`screen`](#screen) is updated once, after the **last** frame.
  With `render=False` the screen keeps showing the frame from the last rendered tick.
  Skipping rendering saves a 2×192 KiB copy and some PIL work. Emulation speed is the same either way.
- With a window, the window is redrawn and its keyboard/mouse input is read on **every** frame.
- `tick(0)` does nothing.
- Returns `True`, or `False` once the window has been closed (the emulator keeps working; call `stop()`).
  Without a window it always returns `True`.

**Raises**

| Exception | When |
|---|---|
| `PymelonDSInvalidOperationException` | the emulator was stopped |
| `PymelonDSInvalidInputException` | `count` is negative or not an integer |

```python
pm.tick()                     # 1 frame
pm.tick(600)                  # 10 seconds
pm.tick(60, render=False)     # 1 second, screen not updated
```

---

### set_emulation_speed

```python
set_emulation_speed(target_speed) -> None
```

Limits emulation to `target_speed` × real time (about 60 fps × `target_speed`). `0` means unlimited.
Floats are allowed (`0.5` = half speed). The default is `1` with a window and `0` without.

**Raises:** `PymelonDSInvalidInputException` if `target_speed` isn't a number ≥ 0.

```python
pm.set_emulation_speed(1)   # real time
pm.set_emulation_speed(0)   # as fast as possible
```

---

### button

```python
button(input: str, delay: int = 1) -> None
```

Presses `input` and releases it `delay` frames later. The press takes effect at the start of the next frame,
so the button is held for exactly `delay` frames.

- `delay` counts **frames**, not `tick()` calls. `pm.button("a", 10); pm.tick(60)` holds A for the first 10
  of those 60 frames.
- `delay=0` presses and releases in the same frame, so the game never sees the press.

**Raises:** `PymelonDSInvalidInputException` for an unknown button name, or a negative or non-integer `delay`.

```python
pm.button("a")              # tap A (1 frame)
pm.button("start", 10)      # hold Start for 10 frames
pm.tick(30)
```

### button_press

```python
button_press(input: str) -> None
```

Holds `input` from the start of the next frame until [`button_release`](#button_release).
Pressing a button that is already held changes nothing.

**Raises:** `PymelonDSInvalidInputException` for an unknown button name.

### button_release

```python
button_release(input: str) -> None
```

Releases `input` from the start of the next frame. Releasing a button that isn't held changes nothing.

**Raises:** `PymelonDSInvalidInputException` for an unknown button name.

```python
pm.button_press("right")
pm.button_press("b")        # run (in many games)
pm.tick(120)
pm.button_release("right")
pm.button_release("b")
pm.tick()
```

Valid names: see [BUTTONS](#buttons). Names are case-insensitive (`"A"`, `"a"`, `"Start"` all work).
More on timing: [Input](input.md).

---

### screen

```python
pm.screen                 # Screen: both screens stacked, top above bottom
pm.screen.top             # top screen
pm.screen.bottom          # bottom (touch) screen
```

Each of the three has the same attributes:

| Attribute | `screen` | `screen.top` / `screen.bottom` |
|---|---|---|
| `.image` | `PIL.Image.Image`, mode `RGBA`, size `(256, 384)` | `PIL.Image.Image`, mode `RGBA`, size `(256, 192)` |
| `.raw_buffer` | `memoryview`, 393 216 bytes | `memoryview`, 196 608 bytes |
| `.raw_buffer_dims` | `(384, 256)` (height, width) | `(192, 256)` |
| `.raw_buffer_format` | `"RGBA"` | `"RGBA"` |

The images are **live views**. They are the same objects every time and their pixels change after each rendered
`tick()`. Use `.copy()` to keep a frame. All three share one buffer, so `screen.image` is always exactly
`top` above `bottom`. The alpha channel is always 255.

Before the first `tick()` the screen is black.

Details and examples: [Screens](screen.md).

---

### save_state

```python
save_state(file_like_object) -> None
```

Writes a full snapshot of the emulator (CPU, RAM, video, sound, cartridge) to a **binary** file-like object and
calls `flush()` on it. A state is about 19 MB.

**Raises**

| Exception | When |
|---|---|
| `PymelonDSInvalidInputException` | a path (`str`/`Path`) or a text-mode file was passed |
| `PymelonDSInvalidOperationException` | the emulator was stopped |
| `PymelonDSException` | melonDS failed to create the state |

```python
with open("state.bin", "wb") as f:
    pm.save_state(f)

buf = io.BytesIO()
pm.save_state(buf)
```

### load_state

```python
load_state(file_like_object) -> None
```

Restores a snapshot made by `save_state`. Reads from the object's **current position** to the end. After writing
to a `BytesIO`, call `seek(0)` first.

- Buttons currently held through the API stay held after loading.
- Presses and releases that are queued or scheduled (for example the release from `button("a", 10)`) are kept.
- `frame_count` is **not** restored. It keeps counting from its current value.
- The screen is updated on the next rendered `tick()`, not immediately.

**Raises**

| Exception | When |
|---|---|
| `PymelonDSInvalidInputException` | a path or a text-mode file was passed |
| `PymelonDSInvalidOperationException` | the emulator was stopped |
| `PymelonDSException` | the data isn't a valid melonDS state or melonDS couldn't load it |

```python
with open("state.bin", "rb") as f:
    pm.load_state(f)

buf.seek(0)
pm.load_state(buf)
```

Savestates vs. battery saves: [States and saves](states-and-saves.md).

---

### stop

```python
stop(save=True, sav_file=None) -> None
```

Stops the emulator, closes the window (if any) and frees the native instance. After `stop()`, `tick`, `save_state` and `load_state` raise
`PymelonDSInvalidOperationException`. Calling `stop()` again does nothing.

- `save=True` writes the cartridge's battery save memory to `sav_file`, or to `self.sav_file` if `sav_file` is
  `None`. If both are `None`, nothing is written.
- `save=False` writes nothing.
- If the write fails, the emulator is still stopped, and then the exception (`PymelonDSException`) is raised.

```python
pm.stop()                         # writes pm.sav_file
pm.stop(save=False)               # discard in-game progress
pm.stop(sav_file="backup.sav")    # write somewhere else
```

> If a `PymelonDS` object is garbage-collected without `stop()`, it's stopped with `save=False`.
> Call `stop()` or use a `with` block if you want in-game saves written.

### Context manager

```python
with PymelonDS("game.nds") as pm:
    pm.tick(600)
# pm.stop() was called here (save=True)
```

`__exit__` calls `stop()` with `save=True`, also when the block ends with an exception.

---

### Attributes

| Attribute | Type | Meaning |
|---|---|---|
| `frame_count` | `int` | Frames emulated since construction. Increased by `tick()`. Not changed by `load_state`. |
| `screen` | `Screen` | See [screen](#screen). |
| `gamerom` | `str` or `None` | ROM path, or `None` if the ROM was given as a file object. |
| `sav_file` | `str` or `None` | Battery save path used at start and by `stop()`. |
| `stopped` | `bool` | `True` after `stop()`. |

---

## BUTTONS

```python
BUTTONS = {
    "a": KEY_A, "b": KEY_B, "x": KEY_X, "y": KEY_Y, "l": KEY_L, "r": KEY_R,
    "start": KEY_START, "select": KEY_SELECT,
    "up": KEY_UP, "down": KEY_DOWN, "left": KEY_LEFT, "right": KEY_RIGHT,
}
```

All 12 DS buttons. The values are the bit masks used by the low-level API
([`KEY_*`](low-level.md#key-bits)). The touch screen, the lid and the power button are not buttons in this API.

---

## Exceptions

```
Exception
└── PymelonDSException                       base class; also raised for errors from melonDS itself
    ├── PymelonDSInvalidInputException       bad argument (unknown button, negative count, path instead of file, ...)
    ├── PymelonDSInvalidOperationException   operation not allowed now (emulator stopped)
    ├── PymelonDSDependencyError             optional dependency missing (PySDL2 for the window)
    └── MelonDSError                         error reported by the native library (melonds_python._bindings)
```

Missing files raise the built-in `FileNotFoundError`.

```python
from melonds_python import PymelonDSException

try:
    pm = PymelonDS("broken.nds")
except FileNotFoundError:
    ...
except PymelonDSException as e:
    print("melonDS error:", e)
```
