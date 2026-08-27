---
name: view-claude-artifact
description: >-
  View, screenshot, and extract the source of a Claude artifact rendering
  (claude.ai/code/artifact/<uuid> URLs), including Claude Design canvases,
  when the Artifact tool's read action fails (e.g. "public (non-member)
  reader ... not enabled" for shared/public artifacts). Use when the user
  shares an artifact link to review, or asks to view an artifact rendering,
  inspect its versions/variants, or pull exact values (colors, tokens,
  tables) out of an artifact page.
---

# View a Claude artifact rendering

Try these in order. Stop at the first level that answers the question.

## 1. Artifact tool

`Artifact` with `action: "read"` works for artifacts the user owns, and returns
a summary for some shared ones. If it fails with the "public (non-member)
reader" error, continue below. WebFetch on the artifact URL hits the same wall
— don't bother. Plain `curl` on the claude.ai URL returns only the SPA shell.

## 2. Screenshot the default state (Orca embedded browser)

The Orca browser uses the user's logged-in claude.ai session:

```
orca goto --url 'https://claude.ai/code/artifact/<uuid>' --json
orca wait --load networkidle --json
orca screenshot --json     # result.data is base64 PNG — decode and Read it
```

Decode: `python3 -c "import json,sys,base64; d=json.load(sys.stdin); open('shot.png','wb').write(base64.b64decode(d['result']['data']))"`

**Known limitation:** the artifact content is a cross-origin iframe
(`*.frame.claudeusercontent.com`). `orca snapshot` cannot see inside it, and
CDP synthetic input (`orca click` / `orca exec --command "mouse ..."`) lands on
the `<iframe>` element in the top frame and never reaches the artifact page —
clicking buttons inside the artifact this way silently does nothing. Do not
keep retrying coordinate clicks; go to level 3.

## 3. Full source + interactive rendering (works every time)

Get the tokenized frame URL from the live page, then curl it — it serves the
complete authored HTML without auth:

```
orca eval --expression "document.querySelector('iframe')?.src" --json
curl -sL -o frame_content.html '<that url>'
```

The file is the artifact's real source (all CSS/JS/tables) — often enough by
itself to answer exact-value questions (grep for hex colors, extract tables).

To interact with UI states (version toggles, theme switches), make it
standalone and render locally:

1. Strip the frame runtime: remove the first two `<script>` blocks
   (`__FRAME_PREAMBLE` + the ~11KB runtime IIFE) and the `<base>` tag. Keep
   the artifact's own scripts.
2. Optionally append `<script>document.getElementById('<btn>').click();</script>`
   before `</body>` to force a state.
3. `orca goto --url "file://$PWD/rendered.html"` — now it's top-level and
   same-origin, so `orca eval` / `orca click` / `orca full-screenshot` all
   work normally.

Notes:
- **Artifacts have published versions, and picking the right one matters.**
  The tokenized frame URL serves exactly one published version — whatever the
  viewer currently shows. If the user names a version (e.g. "pick X in the
  version selector"), that's the viewer's version picker: the dropdown next
  to the artifact title in the TOP frame (visible in `orca snapshot`, so
  `orca click --element <ref>` works on it — it's not inside the artifact
  iframe). Select the named version first, wait, then re-read the iframe src.
  Reading the wrong version can silently disagree with the user's spec.
- The tokenized frame URL is version-stamped; always re-read it from the live
  page rather than reusing a saved one.
- Google Fonts links load fine from `file://`.
- Full-page screenshots of long artifacts: `orca full-screenshot --json`, then
  crop with `sips -c <h> <w> --cropOffset <y> <x>` (offsets/sizes in physical
  pixels; DPR is usually 2).
