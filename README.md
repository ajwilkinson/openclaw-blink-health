# openclaw-blink-health

A small, read-only health check for [Blink](https://blinkforhome.com) cameras, video doorbells
and sync modules. It tells you when a battery is low, a device has gone offline or a WiFi signal
is weak, and stays quiet when everything is fine.

It's one Python file built on [blinkpy](https://github.com/fronzbot/blinkpy), the library behind
Home Assistant's Blink integration, so you don't need Home Assistant to use it. It works on its
own from cron, and comes with a skill for [OpenClaw](https://openclaw.ai) agents.

## Why

Blink cameras run on AA batteries. When Blink marks a battery "low", motion detection often
stops working, but the app only tells you if you go and look. This check reports a low battery
**every time it runs until the batteries are changed**, so it can't be read once and forgotten.

## What it reports

`check` prints one line per problem and nothing when all is well:

| Problem | How often |
|---|---|
| Battery low | Every run, until the batteries are changed |
| Camera, doorbell or sync module offline | Once, until it comes back |
| WiFi weak (1/5 bars or less) on two checks running | Once, until it recovers |
| Saved login no longer works | Once, until you log in again |

```
$ ./blink_health.py check
Blink: camera 'Garage' battery is low: motion detection may not work until the batteries are changed.
```

`status` lists every device:

```
$ ./blink_health.py status
sync module  Home Sync Module: online
camera       Garden: online, battery ok, wifi 4/5, sync link 5/5, 51°F
camera       Garage: online, battery low, wifi 3/5, sync link 5/5, 50°F
camera       Field: online, battery ok, motion detection off, wifi 4/5, sync link 3/5, 51°F
doorbell     Front Doorbell: online, battery ok, wifi 4/5, sync link 5/5
```

`status --json` gives the same as JSON, and `status --raw` prints Blink's whole reply (it
includes serial numbers and account IDs, so don't paste it publicly).

## It only reads

It fetches the account summary Blink's app shows on its home screen. It never wakes the cameras,
downloads clips or thumbnails, or arms, disarms or changes anything. Your password is used once
at login and never stored: only the OAuth tokens are saved, in a file only you can read.

## Install

Needs Python 3.10 or later.

```sh
git clone https://github.com/ajwilkinson/openclaw-blink-health.git
cd openclaw-blink-health
sh setup.sh
.venv/bin/python blink_health.py login
```

`setup.sh` creates a private Python environment in `.venv` and installs blinkpy into it,
so nothing is added to your system Python. On Debian or Ubuntu you may first need
`sudo apt install python3-venv`.

`login` asks for your Blink email, password and the code Blink sends you.

## Run it every morning

```cron
30 7 * * * cd ~/openclaw-blink-health && .venv/bin/python blink_health.py check
```

cron emails you whatever it prints, so you only hear about problems. Or pipe the output to a
notifier of your choice.

## Settings

| Setting | Default |
|---|---|
| `--ignore NAME` (repeatable) | Leave a device out of `check` |
| `BLINK_HEALTH_CREDENTIALS` | `~/.config/blink-health/credentials.json` |
| `BLINK_HEALTH_STATE` | `~/.local/state/blink-health/state.json` |
| `BLINK_HEALTH_WEAK_WIFI` | `1` (bars out of 5 that count as weak) |

## Reading Blink's data

These came from checking the tool against a real account, and may save you some head-scratching
if you work with Blink's API yourself:

- A camera's `status` is `"done"` when all is well, not `"online"`.
- `enabled: false` means **motion detection is switched off**, not that the camera is offline.
  Plenty of people turn it off deliberately on a camera that triggers too often.
- The battery bars (`signals.battery`) often disagree with Blink's own `battery: "ok"/"low"`
  verdict (a camera can say "low" on 3 bars). This tool goes by the verdict, which is what the
  Blink app shows.
- Temperatures are in °F and are sometimes plainly wrong (6°F on a mild morning), so nothing
  here alerts on them.

## Use with OpenClaw

Copy or symlink this folder into your OpenClaw workspace's `skills/` directory. `SKILL.md` tells
the agent how to run the check and how to word the results, and to run `setup.sh` itself the
first time if you haven't. You still do the `login` step yourself, in a terminal, because it
needs your password and the code Blink sends you. Then add a line to a daily
automation, for example: *"Run the blink-health skill's check and tell me about anything it
prints."*

## Not affiliated with Blink

Blink and Amazon have nothing to do with this project. It uses Blink's unofficial cloud API via
blinkpy, which Blink can change at any time.

## Licence

MIT
