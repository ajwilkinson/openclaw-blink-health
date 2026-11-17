---
name: blink-health
description: Blink camera questions: low batteries, cameras offline, weak WiFi, daily camera checks. Read-only health report for Blink cameras, doorbells and sync modules.
homepage: https://github.com/ajwilkinson/openclaw-blink-health
metadata: {"openclaw":{"emoji":"📷","requires":{"bins":["python3"]}}}
---

# Blink camera health (read-only)

Run the script with the Python from this skill's virtual environment: `{baseDir}/.venv/bin/python {baseDir}/blink_health.py <command>`. Each call takes a few seconds.

0. First use: if `{baseDir}/.venv/bin/python` does not exist, run `sh {baseDir}/setup.sh` once (about a minute; it installs blinkpy into a private environment in the skill folder, not the system Python). If it says the venv module is missing, pass on its install instruction to the user rather than running sudo yourself.
1. If the user hasn't logged in yet (the script says `not logged in`), ask them to run `{baseDir}/.venv/bin/python {baseDir}/blink_health.py login` in a terminal themselves. It needs their password and a code Blink sends them, so never ask for either in chat.
2. For "how are my cameras?", run `status` and summarise it in plain words: name the devices that need something done, then say the rest are fine.
3. For scheduled checks, run `check`. It prints one line per problem and nothing when all is well. If it prints nothing, there is nothing to report. Pass `--ignore NAME` for any device the user has asked you to leave out.
4. Put low batteries first and ask the user to change them soon: on Blink cameras a "low" battery usually stops motion detection. Most Blink outdoor cameras take 2x AA lithium batteries. `check` repeats low batteries on every run on purpose, so mention them every time.
5. "motion detection off" is often deliberate (a camera that triggers too often). Mention it only if the user asks about that camera.
6. Ignore the temperature readings unless asked; they are in °F and sometimes wrong.
7. Never use `status --raw` output in chat: it contains serial numbers and account IDs.
8. This skill only reads. It cannot arm, disarm or change cameras; say so if asked.
