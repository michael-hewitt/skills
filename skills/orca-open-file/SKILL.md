---
name: orca-open-file
description: Open a file in the Orca ADE editor for the current worktree. Use when the user wants to open, view, or edit a file in Orca, or says "open in Orca", "show in editor", "open this file".
---

# Open File in Orca ADE

Open a file in the Orca ADE editor, scoped to the current worktree.

## How to open a file

1. First, determine the current worktree by running:

```bash
orca worktree current --json
```

2. Then open the file using a path relative to the worktree root:

```bash
orca file open <relative-path> --worktree current
```

The path must be relative to the worktree root, not absolute.

## Important details

- Paths must be **relative** to the worktree root — absolute paths will fail with `invalid_relative_path`.
- When `--worktree` is omitted, Orca infers the worktree from the current working directory, but prefer passing `--worktree current` explicitly.
- To target a different worktree, use selectors: `id:<id>`, `branch:<branch>`, `issue:<number>`, `path:<path>`, or `active`.
- You can also open diffs with `orca file diff <path>` or all changed files with `orca file open-changed`.

## When to use

- When the user asks to open, view, or edit a file in the editor
- When the user wants to see a file in Orca
- NOT automatically — only when requested
