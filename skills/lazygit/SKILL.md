---
name: lazygit
description: Open lazygit in a new Terminal window for the current repository. Use when the user wants to review diffs, inspect changes, browse git history, or says "lazygit", "show me the diffs", "open lazygit".
---

# Lazygit

Open lazygit in a macOS Terminal window pointed at the current repository. Reuses an existing lazygit window if one is open.

## How to open

Run this exact command via Bash, replacing `REPO_DIR` with the current working directory:

```bash
osascript <<'APPLESCRIPT'
tell application "Terminal"
  set found to false
  repeat with w in windows
    if name of w contains "lazygit" then
      set index of w to 1
      activate
      set found to true
      exit repeat
    end if
  end repeat

  if not found then
    activate
    do script "cd REPO_DIR && lazygit"
    return
  end if
end tell

delay 0.5

tell application "System Events"
  tell process "Terminal"
    keystroke "q"
    delay 1
    keystroke "cd REPO_DIR"
    key code 36
    delay 0.5
    keystroke "lazygit"
    key code 36
  end tell
end tell
APPLESCRIPT
```

## Important details

- First checks for an existing Terminal window with "lazygit" in the title.
- If found: brings it to front, sends `q` to quit lazygit, `cd`s to the repo, and relaunches.
- If not found: opens a new Terminal window with `cd && lazygit`.
- Replace both instances of `REPO_DIR` with the actual working directory path.
- Do NOT use `open -a Terminal.app` — it is unreliable when Terminal is already running.

## When to use

- When the user asks to see diffs or review changes
- When the user explicitly asks for lazygit
- NOT automatically — only when requested
