# States and saves

There are two different kinds of "save":

| | Savestate | Battery save (`.sav`) |
|---|---|---|
| What it is | Snapshot of the **whole emulator** at one frame | The cartridge's save memory: what the **game** writes when you save in-game |
| Created by | `pm.save_state(f)` at any moment | the game itself, when you choose "Save" in the game |
| Restored by | `pm.load_state(f)`, instantly back to that frame | loaded at start-up; the game reads it like a real cartridge |
| Size | about 19 MB | depends on the game (Pokémon Black/White: 512 KiB) |
| Portable | only between PymelonDS / melonDS builds of the same version | the standard `.sav` format, works in other emulators and flashcarts |
| Use it for | checkpoints, retries, branching, exploration | keeping in-game progress between sessions |

## Savestates

```python
import io

# to a file
with open("before_boss.state", "wb") as f:
    pm.save_state(f)
with open("before_boss.state", "rb") as f:
    pm.load_state(f)

# in memory
snap = io.BytesIO()
pm.save_state(snap)
...
snap.seek(0)                  # load_state reads from the current position
pm.load_state(snap)
pm.tick()                     # the screen updates on the next rendered tick
```

Rules:

- The argument must be a **binary** file-like object. A path (`str`/`Path`) or a text-mode file raises
  `PymelonDSInvalidInputException`.
- `save_state` writes, then calls `flush()`. It doesn't close or seek.
- `load_state` reads from the current position to the end of the object.
- After `load_state`:
  - buttons you hold through the API stay held, and queued or scheduled presses and releases are kept
  - `frame_count` is not changed
  - the screen shows the old frame until the next rendered `tick()`
- The battery save memory is part of the state. Loading a state also restores the in-game save data from that
  moment, in memory. The `.sav` file on disk is only changed by `stop()`.
- States are tied to the melonDS version included in this repo. Updating `melonDS/` may make old states fail to
  load.

### Many checkpoints in memory

States are about 19 MB each, so keep that in mind if you hold many:

```python
checkpoints = {}

def checkpoint(name):
    buf = io.BytesIO()
    pm.save_state(buf)
    checkpoints[name] = buf.getvalue()

def restore(name):
    pm.load_state(io.BytesIO(checkpoints[name]))
    pm.tick()
```

States compress well if memory matters (`zlib.compress(buf.getvalue(), 1)`).

## Battery saves (`.sav`)

The `.sav` path is `pm.sav_file`:

- default: the ROM path with `.sav` (`roms/game.nds` → `roms/game.sav`)
- set it explicitly with `PymelonDS(rom, sav_file="...")`
- `None` when the ROM was passed as a file object and no `sav_file` was given (no battery save at all)

Lifecycle:

1. **Start:** if `sav_file` exists, it is loaded into the cartridge.
2. **While running:** the game writes to cartridge memory. **Nothing is written to disk.**
3. **`stop()`** (or the end of a `with` block) writes the cartridge memory to `sav_file`.

```python
with PymelonDS("game.nds") as pm:      # loads game.sav if present
    ...                                # save in-game
# game.sav written here

pm.stop(save=False)                    # throw away in-game progress
pm.stop(sav_file="copy.sav")           # write to a different file
```

> **Important:** if the program crashes or the object is garbage-collected without `stop()`, the `.sav` is
> **not** written. Use `with`, or `try/finally: pm.stop()`.

`stop()` writes the cartridge's save memory even if the game never saved. For a fresh cartridge that is just
empty (`0xFF`) memory, which games treat as "no save".

### Starting fresh vs. continuing

```python
PymelonDS("game.nds", sav_file="runs/run1.sav")   # new file: fresh game
PymelonDS("game.nds", sav_file="runs/run1.sav")   # next time: continues run1
```

Giving every agent run its own `sav_file` keeps runs from overwriting each other's progress.
