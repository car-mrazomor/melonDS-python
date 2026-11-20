# Using it with AI agents

PymelonDS is headless and deterministic. Nothing happens between calls, and the same inputs from the same state
give the same frames. That makes it suitable for agents that look at the screen and choose buttons.

## The basic loop

```python
from melonds_python import PymelonDS

ACTIONS = ["a", "b", "x", "y", "l", "r", "start", "select", "up", "down", "left", "right"]

def observe(pm):
    return pm.screen.image.copy()          # copy: the live image changes on the next tick

def act(pm, action, hold=4, wait=20):
    pm.button(action, hold)
    pm.tick(hold + wait)

with PymelonDS("roms/game.nds", sav_file="runs/agent.sav") as pm:
    pm.tick(600)                            # boot
    while True:
        img = observe(pm)
        action = choose_action(img)         # your model / agent
        if action is None:
            break
        act(pm, action)
```

## Watching it play

Open a window to see what the agent does. Keep the speed unlimited so the window doesn't slow the agent down:

```python
pm = PymelonDS("roms/game.nds", window="SDL2")
pm.set_emulation_speed(0)
```

See [Window](window.md). On macOS, windowed instances must run on the main thread.

## Choosing what the model sees

| Option | Code | Notes |
|---|---|---|
| Both screens | `pm.screen.image` | 256×384. Simplest; the model sees everything. |
| Top only | `pm.screen.top.image` | Often enough when the bottom screen is a static menu. |
| Bottom only | `pm.screen.bottom.image` | Menus, maps, touch UIs. |
| Upscaled | `img.resize((512, 768), Image.NEAREST)` | Vision models read pixel text better when it's bigger. |
| As PNG bytes | see below | For APIs that take base64 images. |

```python
import base64, io

def to_png_b64(img):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
```

Tell the model which half is which when you send the stacked image ("top half: top screen, bottom half: touch
screen").

## Timing tips

- **Wait after acting.** Animations, text boxes and transitions take time. `wait=20..60` frames after a press
  avoids sending the next action before the game is ready.
- **Wait for the screen to settle** instead of guessing:

  ```python
  def wait_until_stable(pm, frames=6, max_wait=300):
      last = pm.screen.image.tobytes()
      stable = 0
      for _ in range(max_wait):
          pm.tick()
          now = pm.screen.image.tobytes()
          stable = stable + 1 if now == last else 0
          if stable >= frames:
              return
          last = now
  ```

  Some screens animate forever (water, blinking cursors), so keep `max_wait`.
- **Skip rendering while waiting:** `pm.tick(n, render=False)` and then `pm.tick()` to get a fresh frame.
- **Speed:** with the JIT a frame takes about 1 ms, so the model call is almost always the bottleneck,
  not the emulator.

## Checkpoints and retries

Savestates are cheap enough to take before risky actions:

```python
import io

def snapshot(pm):
    buf = io.BytesIO()
    pm.save_state(buf)
    return buf.getvalue()

def restore(pm, data):
    pm.load_state(io.BytesIO(data))
    pm.tick()

safe = snapshot(pm)
act(pm, "a")
if looks_bad(observe(pm)):
    restore(pm, safe)
```

Each state is about 19 MB. Keep a small rolling window, or write them to disk.

Keep in-game progress with the battery save: give the run its own `sav_file` and make sure `stop()` runs
(use `with`). See [States and saves](states-and-saves.md).

## Several emulators at once

Multiple `PymelonDS` instances can run in one process (tested with and without the JIT). Each has its own state,
screen and save file:

```python
envs = [PymelonDS("roms/game.nds", sav_file=f"runs/{i}.sav") for i in range(4)]
for pm in envs:
    pm.tick(600)
```

Use one instance per thread. Don't call the same instance from several threads at once. For real
parallelism across CPU cores, use processes (`multiprocessing`) with one emulator each.

## Logging the run

```python
import json, time
from pathlib import Path

log_dir = Path("runs/log"); log_dir.mkdir(parents=True, exist_ok=True)

def log_step(pm, step, action, note=""):
    pm.screen.image.save(log_dir / f"{step:06d}.png")
    with open(log_dir / "steps.jsonl", "a") as f:
        f.write(json.dumps({"step": step, "frame": pm.frame_count, "action": action,
                            "note": note, "t": time.time()}) + "\n")
```

## What the agent can't do (yet)

- **Touch:** `PymelonDS` has no touch API. Games that need the stylus can't be fully played through it.
- **Reading game memory:** not part of `PymelonDS`. The low-level `Core` can read RAM
  ([Low-level API](low-level.md#memory)).
- **Sound:** not part of `PymelonDS`.
