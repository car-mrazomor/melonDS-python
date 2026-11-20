# Coming from PyBoy

PymelonDS copies PyBoy's API for the parts it has, so a lot of PyBoy code ports by renaming the class.

```python
# PyBoy
from pyboy import PyBoy
pyboy = PyBoy("game.gb", window="null")

# PymelonDS
from melonds_python import PymelonDS
pm = PymelonDS("game.nds")
```

## The same

| | PyBoy | PymelonDS |
|---|---|---|
| Run frames | `tick(count=1, render=True)` | `tick(count=1, render=True)` |
| Speed limit | `set_emulation_speed(n)`, 0 = unlimited; 1× with a window, unlimited with `"null"` | same |
| Tap a button | `button(input, delay=1)` | `button(input, delay=1)` |
| Hold / release | `button_press`, `button_release` | `button_press`, `button_release` |
| Input timing | applied at the start of the next frame | same |
| Button names | case-insensitive strings | same, plus `x`, `y`, `l`, `r` |
| Screen image | `screen.image` (live RGBA PIL image) | `screen.image` (live RGBA PIL image) |
| Raw pixels | `screen.raw_buffer`, `raw_buffer_dims`, `raw_buffer_format` | same |
| States | `save_state(f)` / `load_state(f)` with binary file objects | same, with the same checks for paths and text files |
| Battery save | loaded at start, written on `stop()` | same |
| Stop | `stop(save=True)`, context manager, `__del__` stops without saving | same |
| Frame counter | `frame_count` | `frame_count` |
| ROM argument | path or file object | path or file object |

## Different

| | PyBoy | PymelonDS |
|---|---|---|
| Screens | one 160×144 | `screen` = both stacked 256×384, plus `screen.top` and `screen.bottom` (256×192 each) |
| Buttons | 8 | 12 (`a b x y l r start select up down left right`) |
| Window | `window="SDL2"`, `"OpenGL"`, `"null"`, ...; default `"SDL2"` | `window="SDL2"` or `"null"`; default **`"null"`** |
| Window scale | `scale=3` | `scale=2` |
| Battery save file | `ram_file=` argument, default `<rom>.ram` | `sav_file=` argument, default ROM path with `.sav` |
| `stop()` arguments | `stop(save=True, ram_file=None, rtc_file=None)` | `stop(save=True, sav_file=None)` |
| ROM as file object, no save path | `stop()` fails (`None + ".ram"`) | no battery save is used; `stop()` writes nothing |
| `tick()` return value | `False` once the window is closed (and for `tick(0)`) | `False` once the window is closed; `tick(0)` returns `True` |
| Window keys | `A`=a, `S`=b, Enter, Backspace, arrows | melonDS layout: `X`=A, `Z`=B, `S`=X, `A`=Y, `Q`=L, `W`=R, Enter, Backspace, arrows; mouse = touch |
| Sound | `sound` argument to `tick`, `pyboy.sound` | none |
| `screen.ndarray` | yes (numpy) | no; use `np.asarray(pm.screen.image)` |
| Memory | `pyboy.memory[...]` | not in `PymelonDS` ([low-level](low-level.md#memory) only) |
| Game wrappers, plugins, symbols, tilemaps, sprites, `send_input`, hooks | yes | no |
| Touch screen | n/a | not in `PymelonDS` ([low-level](low-level.md#input) only) |
| Exceptions | `PyBoyException` and subclasses | `PymelonDSException`, `PymelonDSInvalidInputException`, `PymelonDSInvalidOperationException` |

## Porting checklist

1. `PyBoy(rom, window="null", ...)` → `PymelonDS(rom)`. `window="SDL2"` and `scale` work too. Remove `sound*`,
   `cgb` and palette options. Note that PymelonDS defaults to **no window**.
2. `ram_file=` → `sav_file=`.
3. Screen sizes: 160×144 → 256×384 (or 256×192 for `top`/`bottom`). Fix crops and coordinates.
4. `screen.ndarray` → `np.asarray(pm.screen.image)`.
5. Replace `pyboy.memory[...]` reads with screen-based logic, or use the low-level `Core`.
6. Timing values usually need retuning: DS games react at different speeds than Game Boy games.
