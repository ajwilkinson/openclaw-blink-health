#!/usr/bin/env python3
"""Read-only health check for Blink cameras, doorbells and sync modules, via blinkpy.

Usage:
  blink_health.py login                 one-off interactive login (email, password, 2FA code).
                                        Saves OAuth tokens only, never the password.
  blink_health.py status [--json|--raw] every device: online, battery, motion detection, signal
  blink_health.py check [--ignore NAME ...]
                                        prints one line per problem worth telling someone about,
                                        and nothing when all is well. Made for cron jobs and agents.

What `check` reports:
  - a low battery, on EVERY run until the batteries are changed (a low battery usually means
    motion detection has stopped working, so it shouldn't be mentioned once and forgotten)
  - a device offline, once until it comes back
  - WiFi signal weak on two checks running, once until it recovers
  - the saved login no longer working

Only the account's home-screen summary is read from Blink's cloud. It never wakes the cameras,
downloads thumbnails or clips, arms, disarms or changes anything.

Settings (environment):
  BLINK_HEALTH_CREDENTIALS  token file   (default ~/.config/blink-health/credentials.json)
  BLINK_HEALTH_STATE        state file   (default ~/.local/state/blink-health/state.json)
  BLINK_HEALTH_WEAK_WIFI    bars out of 5 at or below which WiFi counts as weak (default 1)
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

from aiohttp import ClientSession
from blinkpy.auth import Auth, BlinkTwoFARequiredError
from blinkpy.blinkpy import Blink

CRED = Path(os.environ.get("BLINK_HEALTH_CREDENTIALS",
                           Path.home() / ".config/blink-health/credentials.json")).expanduser()
STATE = Path(os.environ.get("BLINK_HEALTH_STATE",
                            Path.home() / ".local/state/blink-health/state.json")).expanduser()
WEAK_WIFI = int(os.environ.get("BLINK_HEALTH_WEAK_WIFI", "1"))
TOKEN_KEYS = ("token", "expires_in", "expiration_date", "refresh_token", "host", "region_id",
              "client_id", "account_id", "user_id", "hardware_id", "uid", "device_id", "username")


def save_tokens(auth, old_refresh=None):
    data = {k: v for k, v in auth.login_attributes.items() if k in TOKEN_KEYS}
    if not data.get("refresh_token") and old_refresh:
        data["refresh_token"] = old_refresh  # a refresh reply may not include a new one
    CRED.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = CRED.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, CRED)


async def login():
    email = input("Blink email: ").strip()
    password = getpass("Blink password (not shown): ")
    async with ClientSession() as session:
        blink = Blink(session=session)
        blink.auth = Auth({"username": email, "password": password}, no_prompt=True, session=session)
        try:
            ok = await blink.start()
        except BlinkTwoFARequiredError:
            code = input("Code Blink just sent you: ").strip()
            ok = await blink.send_2fa_code(code)
        if not ok or not blink.auth.refresh_token:
            print("Login failed. Nothing saved.")
            return 1
        save_tokens(blink.auth)
        print(f"Logged in. Tokens saved to {CRED} (password not stored).")
        print(f"Found {len(blink.cameras)} camera(s): {', '.join(blink.cameras) or 'none'}")
        return 0


async def fetch_homescreen():
    """Return (homescreen dict, None) or (None, error text)."""
    if not CRED.exists():
        return None, "not logged in (run: blink_health.py login)"
    data = json.loads(CRED.read_text())
    old_refresh = data.get("refresh_token")
    async with ClientSession() as session:
        blink = Blink(session=session)
        blink.auth = Auth(data, no_prompt=True, session=session)
        try:
            await blink.auth.startup()  # OAuth refresh with the saved token; no password held
            blink.setup_urls()
            await blink.get_homescreen()
        except Exception as e:  # noqa: BLE001 - any failure here means the login no longer works
            return None, f"Blink login no longer works ({type(e).__name__}); run: blink_health.py login"
        finally:
            if blink.auth.refresh_token:
                save_tokens(blink.auth, old_refresh)
    hs = blink.homescreen
    if not isinstance(hs, dict) or "cameras" not in hs:
        return None, "Blink returned an unexpected reply (the API may have changed)"
    return hs, None


def bars(v):
    return v if isinstance(v, int) else None


def summarise(hs):
    """Flatten the home screen into one list of devices."""
    nets = {n.get("id"): n.get("name") for n in hs.get("networks", [])}
    out = []
    for s in hs.get("sync_modules", []):
        out.append({"kind": "sync module", "name": s.get("name") or nets.get(s.get("network_id")),
                    "online": s.get("status") == "online", "status": s.get("status"),
                    "battery": None, "wifi": bars((s.get("signals") or {}).get("wifi")),
                    "lfr": None, "temp": None})
    for kind, key in (("camera", "cameras"), ("doorbell", "doorbells"), ("mini", "owls")):
        for c in hs.get(key, []):
            sig = c.get("signals") or {}
            status = c.get("status")
            out.append({"kind": kind, "name": (c.get("name") or "").strip(),
                        # status is "done" when all is well; enabled=False only means motion
                        # detection is switched off, not that the camera is offline
                        "online": status not in ("offline", "disconnected"),
                        "motion_off": c.get("enabled", True) is False,
                        "status": status, "battery": c.get("battery"),
                        "battery_bars": bars(sig.get("battery")), "wifi": bars(sig.get("wifi")),
                        "lfr": bars(sig.get("lfr")), "temp": sig.get("temp"),
                        "issues": c.get("issues") or []})
    return out


def print_status(devs):
    for d in devs:
        bits = ["online" if d["online"] else f"OFFLINE ({d['status']})"]
        if d.get("battery"):
            # Blink's own ok/low verdict; the battery bars often disagree with it, so not shown
            bits.append(f"battery {d['battery']}")
        if d.get("motion_off"):
            bits.append("motion detection off")
        if d.get("wifi") is not None:
            bits.append(f"wifi {d['wifi']}/5")
        if d.get("lfr") is not None:
            bits.append(f"sync link {d['lfr']}/5")
        if d.get("temp") is not None:
            bits.append(f"{d['temp']}°F")
        if d.get("issues"):
            bits.append(f"issues: {d['issues']}")
        print(f"{d['kind']:12} {d['name']}: " + ", ".join(bits))


def check(devs, err, ignore=()):
    """Print problems that need telling. Low batteries repeat every check; other warnings once until they clear."""
    try:
        st = json.loads(STATE.read_text())
    except (FileNotFoundError, ValueError):
        st = {}
    warned, weak_prev = set(st.get("warned", [])), set(st.get("weak", []))
    now_problems, weak_now, msgs = set(), set(), []
    ignore = {i.strip().lower() for i in ignore}

    def flag(key, text, repeat=False):
        now_problems.add(key)
        if repeat or key not in warned:
            msgs.append(text)

    if err:
        flag("login", f"Blink: {err}.")
    else:
        for d in devs:
            if (d["name"] or "").lower() in ignore:
                continue
            n = f"{d['kind']} '{d['name']}'"
            if not d["online"]:
                flag(f"offline:{d['name']}", f"Blink: {n} is offline.")
            if d.get("battery") and str(d["battery"]).lower() not in ("ok", "none"):
                # repeated every check until changed: a low battery stops motion detection
                flag(f"battery:{d['name']}", f"Blink: {n} battery is {d['battery']}: "
                     "motion detection may not work until the batteries are changed.", repeat=True)
            if d.get("wifi") is not None and d["wifi"] <= WEAK_WIFI and d["online"]:
                weak_now.add(d["name"])
                if d["name"] in weak_prev:  # weak on two checks running
                    flag(f"weak:{d['name']}", f"Blink: {n} WiFi signal weak ({d['wifi']}/5) two checks running.")
    for m in msgs:
        print(m)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"warned": sorted(now_problems), "weak": sorted(weak_now),
                                 "checked": datetime.now().isoformat(timespec="seconds"),
                                 "devices": devs}, indent=1))


def option_values(args, flag):
    return [args[i + 1] for i, a in enumerate(args[:-1]) if a == flag]


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if cmd == "login":
        return asyncio.run(login())
    if cmd not in ("status", "check"):
        print(f"Unknown command {cmd!r}. Try: login, status, check, --help", file=sys.stderr)
        return 2
    hs, err = asyncio.run(fetch_homescreen())
    devs = summarise(hs) if hs else []
    if cmd == "check":
        check(devs, err, option_values(args, "--ignore"))
        return 0
    if err:
        print(err)
        return 1
    if "--raw" in args:
        print(json.dumps(hs, indent=1))
    elif "--json" in args:
        print(json.dumps(devs, indent=1))
    else:
        print_status(devs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
