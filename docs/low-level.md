# Low-level API

Below `PymelonDS` there are two thinner layers:

```text
PymelonDS                      melonds_python/pymelonds.py    PyBoy-style API
   │
_bindings.Core                 melonds_python/_bindings.py    ctypes wrapper, 1:1 with the C API
   │
libmelonds_py (mds_* C API)    native/melonds_shim.h/.cpp     C shim over the melonDS core
   │
melonDS core (C++)             melonDS/src
```

Use these if you need something `PymelonDS` doesn't expose: **touch, memory, audio, lid, reset**. They are
internal (the underscore in `_bindings`), so their interface may change.

> A `PymelonDS` object keeps its `Core` private. Use `Core` directly instead of mixing the two on the same
> emulator.

---

## `_bindings.Core`

```python
from melonds_python import _bindings as mds

core = mds.Core(bios9=None, bios7=None, firmware=None, jit=True)
core.load_rom("roms/game.nds", "roms/game.sav")
for _ in range(600):
    core.run_frame()
top, bottom = core.screens()
core.close()
```

Errors raise `mds.MelonDSError` (a subclass of `PymelonDSException`) with melonDS's message.
`Core` does **not** check paths or arguments beyond what the C side does.

### Lifecycle

| Method | Description |
|---|---|
| `Core(bios9=None, bios7=None, firmware=None, jit=True)` | Create an emulator. `None` uses FreeBIOS / generated firmware. Raises `MelonDSError` for unreadable or wrong-size BIOS files or invalid firmware. |
| `load_rom(rom, sav=None)` | Load a ROM from a path and boot it. If `sav` exists it's loaded. Nothing is written back automatically. |
| `load_rom_bytes(data, sav=None)` | Same, from bytes. |
| `reset()` | Reboot the loaded ROM (cartridge save memory is kept in RAM). Resets the native frame counter. |
| `write_save(sav)` | Write the cartridge's save memory to a file. Does nothing if the cartridge has no save memory. |
| `close()` | Free the emulator. Also called by `__del__`. Afterwards most methods do nothing or return 0, and `load_rom`/`save_state` raise `MelonDSError`. Don't use the object after closing it. |

### Emulation

| Method | Description |
|---|---|
| `run_frame() -> int` | Emulate one frame. Returns the number of scanlines run (normally 263). Returns 0 if no ROM is loaded. |
| `frame_count() -> int` | Frames since the ROM was loaded or reset. |

### Input

| Method | Description |
|---|---|
| `set_keys(mask)` | Set **all** held buttons at once (`1` = pressed). Takes effect for the next `run_frame()`. |
| `get_keys() -> int` | The current mask. |
| `touch(x, y)` | Touch the bottom screen at `x` 0–255, `y` 0–191 (values are clamped). Stays touched until `release_touch()`. |
| `release_touch()` | Lift the stylus. |
| `set_lid_closed(closed)` | Close or open the lid. Many games pause or sleep when it's closed. |

#### Key bits

| Constant | Bit | Constant | Bit |
|---|---|---|---|
| `KEY_A` | 0 | `KEY_UP` | 6 |
| `KEY_B` | 1 | `KEY_DOWN` | 7 |
| `KEY_SELECT` | 2 | `KEY_R` | 8 |
| `KEY_START` | 3 | `KEY_L` | 9 |
| `KEY_RIGHT` | 4 | `KEY_X` | 10 |
| `KEY_LEFT` | 5 | `KEY_Y` | 11 |

```python
core.set_keys(mds.KEY_A | mds.KEY_RIGHT)
core.run_frame()
core.set_keys(0)
```

Tapping the touch screen:

```python
core.touch(128, 150)
for _ in range(5):
    core.run_frame()
core.release_touch()
core.run_frame()
```

Dragging: call `touch(x, y)` with new coordinates before each `run_frame()`.

### Video

| Method | Description |
|---|---|
| `screens() -> (bytes, bytes)` | Copy of the last finished frame: top and bottom, RGBA, 256×192 each (196 608 bytes). |
| `screens_into(top, bottom)` | Copy into your own writable buffers (`bytearray`, writable `memoryview`, ctypes array) of 196 608 bytes each. Either may be `None`. No allocations. |

```python
from PIL import Image
top, bottom = core.screens()
Image.frombytes("RGBA", (256, 192), top).save("top.png")
```

Constants: `SCREEN_WIDTH = 256`, `SCREEN_HEIGHT = 192`, `SCREEN_BYTES = 196608`.

### Audio

melonDS produces interleaved stereo signed 16-bit samples at 48 000 Hz, about 800 sample frames per video frame.

| Method | Description |
|---|---|
| `audio_available() -> int` | Sample frames waiting in the buffer. |
| `read_audio(max_frames=4096) -> bytes` | Take up to `max_frames` sample frames (4 bytes each: L, R). |

The internal buffer holds about 2 000 sample frames (2.5 video frames). When it's full the oldest samples are
dropped. Read after every frame if you want continuous sound.

```python
import wave

w = wave.open("out.wav", "wb")
w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
for _ in range(600):
    core.run_frame()
    w.writeframes(core.read_audio())
w.close()
```

### Savestates

| Method | Description |
|---|---|
| `save_state() -> bytes` | Full snapshot (about 19 MB). |
| `load_state(data)` | Restore a snapshot. Held keys (`set_keys`) are re-applied afterwards. |

### Memory

| Method | Description |
|---|---|
| `read8/16/32(addr) -> int` | Read through the ARM9 bus (same view as the game's main CPU). |
| `write8/16/32(addr, value)` | Write through the ARM9 bus. |
| `main_ram() -> memoryview` | Live, writable view of main RAM (4 MiB on DS). Valid only while the `Core` is alive. |

Main RAM is mapped at `0x02000000`–`0x023FFFFF`. `main_ram()[i]` is the byte at `0x02000000 + i`.

```python
ram = core.main_ram()
value = int.from_bytes(ram[0x1000:0x1004], "little")    # same as core.read32(0x02001000)
```

> Reading I/O registers (`0x04xxxxxx`) through `read*` can have side effects, as on hardware.
> Writing memory can crash the game. It's meant for inspection and cheats.

### Logging

```python
mds.set_log_level(0)   # 0 debug, 1 info, 2 warn (default), 3 error, 4 silent
```

Messages go to stderr. The setting is global for the process.

---

## C API (`native/melonds_shim.h`)

For use from C, C++ or another language's FFI. All functions are `extern "C"` and exported from
`libmelonds_py`. Functions returning `int` use `0` = success and `-1` = error. After an error,
`mds_last_error()` returns a message (per thread).

```c
typedef struct mds_t mds_t;

const char* mds_last_error(void);
void        mds_set_log_level(int level);

mds_t*   mds_create(const char* bios9, const char* bios7, const char* firmware, int use_jit);  // NULL on error
void     mds_destroy(mds_t* m);

int      mds_load_rom(mds_t* m, const char* rom_path, const char* sav_path);
int      mds_load_rom_mem(mds_t* m, const uint8_t* data, uint32_t len, const char* sav_path);
int      mds_write_save(mds_t* m, const char* sav_path);
int      mds_reset(mds_t* m);

uint32_t mds_run_frame(mds_t* m);
uint64_t mds_frame_count(mds_t* m);

void     mds_set_keys(mds_t* m, uint32_t pressed_mask);   // MDS_KEY_* bits, 1 = pressed
uint32_t mds_get_keys(mds_t* m);
void     mds_touch(mds_t* m, int x, int y);
void     mds_release_touch(mds_t* m);
void     mds_set_lid_closed(mds_t* m, int closed);

int      mds_get_screens(mds_t* m, uint8_t* top_rgba, uint8_t* bottom_rgba);  // 256*192*4 bytes each, NULL to skip

int      mds_audio_available(mds_t* m);
int      mds_read_audio(mds_t* m, int16_t* out, int max_frames);          // returns frames read

int      mds_save_state(mds_t* m, uint8_t** out, uint32_t* out_len);     // free *out with mds_free
int      mds_load_state(mds_t* m, const uint8_t* data, uint32_t len);
void     mds_free(void* p);

uint8_t  mds_read8 (mds_t* m, uint32_t addr);
uint16_t mds_read16(mds_t* m, uint32_t addr);
uint32_t mds_read32(mds_t* m, uint32_t addr);
void     mds_write8 (mds_t* m, uint32_t addr, uint8_t  val);
void     mds_write16(mds_t* m, uint32_t addr, uint16_t val);
void     mds_write32(mds_t* m, uint32_t addr, uint32_t val);
uint32_t mds_main_ram(mds_t* m, uint8_t** out);                         // returns size
```

Minimal C example:

```c
#include "melonds_shim.h"
#include <stdio.h>

int main(void) {
    mds_t* m = mds_create(NULL, NULL, NULL, 1);
    if (!m || mds_load_rom(m, "game.nds", NULL) != 0) {
        fprintf(stderr, "error: %s\n", mds_last_error());
        return 1;
    }
    static uint8_t top[256 * 192 * 4], bottom[256 * 192 * 4];
    for (int i = 0; i < 600; i++) mds_run_frame(m);
    mds_get_screens(m, top, bottom);
    mds_destroy(m);
    return 0;
}
```

Threading: an `mds_t` must not be used from two threads at the same time. Separate instances are independent.
