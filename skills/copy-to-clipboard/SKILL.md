---
name: copy-to-clipboard
description: Put text on the macOS clipboard as rich text (RTF) or plain text, ready to paste into email, docs, or chat. Use when the user asks to copy something to the clipboard, wants formatted or rich text on the clipboard, says "copy that to the clipboard" or "put it on my clipboard", or asks for a snippet ready to paste into Gmail, Word, Notes, or Slack.
---

# Copy to clipboard (macOS)

## Rich text

Write the content as an HTML fragment to a scratch file, then convert and copy:

```bash
textutil -format html -inputencoding UTF-8 -convert rtf -stdout snippet.html \
  | pbcopy -Prefer rtf
```

Verify it landed as rich text before telling the user it worked:

```bash
osascript -e 'the clipboard as «class RTF »' >/dev/null && echo "OK: rich text on clipboard"
```

`pbcopy` needs the real pasteboard, so run these with the sandbox disabled.

## Use ASCII punctuation only

**This is the rule that actually bites.** `textutil` emits RTF declaring `\ansicpg1252`, and
every non-ASCII character becomes a single-byte escape — an em dash turns into `\'97`. Any
paste target that ignores the declared codepage and assumes MacRoman renders `\'97` as `ó`.
The user sees stray accented letters scattered through the text.

HTML entities do not help: `&mdash;` and `&#8212;` both produce the same `\'97`. There is no
safe way to encode an em dash. Do not use one.

Substitute plain ASCII throughout:

| Avoid | Escape produced | Use instead |
|---|---|---|
| — em dash | `\'97` | ` -- `, or restructure the sentence |
| – en dash | `\'96` | `-`, or "to" in ranges |
| " " ' ' curly quotes | `\'93` `\'94` `\'92` | `"` and `'` |
| … ellipsis | `\'85` | `...` |
| → ✓ • arrows, checks, bullets | varies | words, or `<ul>` for lists |
| non-breaking space | `\'a0` | a normal space |

Formatting is safe — `<b>`, `<i>`, `<ol>`, `<ul>`, `<table>`, and inline CSS all survive the
conversion. It is only the characters that break.

## Setting a font: sizes are in `px`, not `pt`

When the user asks for a specific font ("Helvetica 12pt"), wrap the fragment in a single
`<div>` with inline CSS. That is enough — the style inherits into paragraphs and into table
cells, so there is no need to repeat it on every element.

**`textutil` reads a CSS `pt` value as if it were `px`, then converts px to pt at 4/3.** So
`font-size: 12pt` lands in the RTF as 16pt — a third too big. Express the size the user asked
for in `px` and it comes out correct:

```html
<div style="font-family: Helvetica, sans-serif; font-size: 12px;">
  ... fragment ...
</div>
```

| You write | RTF result | Pasted size |
|---|---|---|
| `font-size: 12pt` | `\fs32` | 16pt (wrong) |
| `font-size: 12px` | `\fs24` | 12pt (right) |

Verify before reporting success. RTF `\fsNN` is in half-points, so halve it to get the point
size, and check the font table names the family you asked for:

```bash
textutil -format html -inputencoding UTF-8 -convert rtf -stdout snippet.html \
  | rg -o 'fonttbl.*|fs[0-9]+' | head -3
```

## Always pass `-inputencoding UTF-8`

Without it `textutil` misreads the file as Latin-1 and each literal UTF-8 character becomes
three garbage escapes (`\'e2\'80\'9c` for a curly quote). The flag costs nothing and prevents
a whole class of corruption, so include it every time even when the content looks like clean
ASCII.

## Rich text leaves no plain-text fallback

`pbcopy -Prefer rtf` puts *only* the RTF flavor on the pasteboard — `pbpaste` returns empty.
Pasting into a terminal, a code editor, or any plain-text field yields nothing at all.

So pick one based on where it is going:

- Email, Google Docs, Word, Notes, Slack → rich text, as above.
- Terminal, editor, chat that renders its own markdown → plain text: `pbcopy < snippet.md`.

If the user needs both, ask which target matters; do not silently choose.

## After copying

Show the user the content in your reply, as markdown. They cannot see the clipboard, and
confirming what landed there is how they catch a wrong-snippet mistake before pasting it in
front of someone else.
