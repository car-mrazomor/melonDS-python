# Input

## Buttons

| Name | DS button |
|---|---|
| `a`, `b`, `x`, `y` | face buttons |
| `l`, `r` | shoulder buttons |
| `start`, `select` | Start, Select |
| `up`, `down`, `left`, `right` | D-pad |

Names are case-insensitive. Anything else raises `PymelonDSInvalidInputException`.

The touch screen has no API in `PymelonDS` (it's available only in the [low-level API](low-level.md#input)).

## The three calls

| Call | Effect |
|---|---|
| `button(name, delay=1)` | press now, release `delay` frames later |
| `button_press(name)` | press, keep held |
| `button_release(name)` | release |

None of them emulate anything. They queue a change that is applied during the next `tick()`.

## Timing

The DS reads input once per frame. PymelonDS works the same way PyBoy does:

1. `button_press` / `button_release` / `button` put a press or release in a queue.
2. At the **start of each frame** inside `tick()`, all queued changes are applied, then the frame runs.
3. A release scheduled with `button(name, delay)` is due when `frame_count` reaches
   `frame_count_at_call + delay`, and is applied at the start of the frame after that.

So **`button(name, delay)` holds the button for exactly `delay` frames**, counted from the next frame.

```text
pm.button("a", 3)
pm.tick(5)

frame:     1    2    3    4    5
A held:    ■    ■    ■    ·    ·
```

```text
pm.button_press("a")
pm.tick(2)
pm.button_release("a")
pm.tick(2)

frame:     1    2  | 3    4
A held:    ■    ■  | ·    ·
```

### Things to know

- **`delay` is in frames, not ticks.** `button("a", 10); tick(1); tick(1); ...` releases after 10 frames no matter
  how many `tick()` calls that takes.
- **Calls without a `tick()` in between are combined.** Press then release before the next frame means the game
  never sees the button:

  ```python
  pm.button_press("a")
  pm.button_release("a")
  pm.tick()                 # A is NOT pressed in this frame
  ```

  That's also why `button("a", 0)` does nothing.
- **Several buttons at once:** just queue them all before the `tick()`.

  ```python
  pm.button("l", 5)
  pm.button("r", 5)
  pm.tick(5)                # L+R held together for 5 frames
  ```

- **Holding across ticks:** a pressed button stays pressed until released, across any number of `tick()` calls.
- **`load_state`** keeps whatever you are holding through the API and keeps queued and scheduled changes.

## How long to hold

Most games react to a button that is held for 1 frame, but some need several, especially during fades or
on menus that debounce input. Some practical defaults:

| Situation | Typical approach |
|---|---|
| Menu / dialogue | `button("a", 2)`, then `tick(20..60)` before the next press |
| Walking one step | a short hold (a few to ~16 frames), then some idle frames. Measure it for your game. |
| Walking a distance | `button_press("up")`, `tick(n)`, `button_release("up")` |
| Mashing through text | loop `button("a", 2); tick(10)` |

If presses get lost, increase the hold time or wait longer after transitions. If a game moves twice, decrease it.

## Examples

Walk right for one second while holding B:

```python
pm.button_press("right")
pm.button_press("b")
pm.tick(60)
pm.button_release("right")
pm.button_release("b")
pm.tick()
```

Mash A through an intro:

```python
for _ in range(30):
    pm.button("a", 2)
    pm.tick(15, render=False)
pm.tick()   # render once at the end
```

A tiny "action" helper for scripts and agents:

```python
def act(pm, name, hold=4, wait=20):
    pm.button(name, hold)
    pm.tick(hold + wait)
    return pm.screen.image.copy()
```
