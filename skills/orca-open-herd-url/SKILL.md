# Open Laravel Herd URL in Orca Browser

Open the Laravel Herd development server URL for the current Orca worktree in a browser tab scoped to that worktree.

## How to open the Herd URL

1. Get the current worktree path:

```bash
orca worktree current --json
```

2. Extract the directory name from the worktree `path` field. Laravel Herd serves parked directories as `http://<dirname>.test`.

3. Open the URL in an Orca browser tab scoped to the current worktree:

```bash
orca tab create --url "http://<dirname>.test" --worktree current
```

## Important details

- Use **`http://`**, not `https://` — Laravel Herd uses plain HTTP by default unless the site has been explicitly secured.
- The `--worktree current` flag ensures the tab opens in the correct workspace, even if the user switches workspaces before the tab opens.
- The directory name is the last path component of the worktree path (e.g., `/Users/michael/orca/workspaces/project/my-feature-branch` → `my-feature-branch`).
- If the user provides a specific path (e.g., `/login`, `/admin`), append it to the URL: `http://<dirname>.test/login`.

## When to use

- When the user asks to open the app, preview the site, open the dev server, or view the local site in a browser
- When you need to visually verify UI changes
- NOT automatically — only when requested or when the task requires visual verification
