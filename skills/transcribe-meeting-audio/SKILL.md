---
name: transcribe-meeting-audio
description: >-
  Transcribe a meeting, call, or voice-memo audio file (m4a, mp3, wav, mp4) into a
  timestamped transcript, then produce a cleaned, speaker-attributed transcript plus
  secretarial meeting notes. Use this whenever the user attaches or points to an audio
  recording and wants it transcribed, processed, summarized, or turned into notes or
  minutes — including phrases like "here's the recording", "process this audio",
  "transcribe my voice memo", "what did we decide in this meeting", or an audio file
  appearing with a meeting-like name. Speech-to-text runs locally in the sandbox
  (sherpa-onnx + Whisper via GitHub-hosted models), so do not tell the user
  transcription is impossible or send them to an external transcription service
  before following this skill.
---

# Transcribe meeting audio

Turn a raw audio recording into three things: a timestamped raw transcript, a cleaned speaker-attributed transcript, and secretarial notes. The pipeline runs entirely in the sandbox. It exists because the usual Whisper model hosts (HuggingFace, OpenAI's CDN) are blocked by the sandbox egress allowlist, but GitHub release assets are reachable — and the k2-fsa/sherpa-onnx project publishes ready-to-run Whisper ONNX models there.

The work has two halves. The mechanical half (steps 1–4) is scripted. The judgment half (step 5) is where the value and the risk live: cleaning garbled machine transcription without inventing content.

## Step 1 — Setup (once per session)

```bash
pip install sherpa-onnx numpy --break-system-packages -q
curl -sL -o silero_vad.onnx https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx
curl -sL -o model.tar.bz2 https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-base.en.tar.bz2
tar xjf model.tar.bz2
```

Model choice: base.en (~200 MB, ≈ audio-length ÷ 2 compute on 2 cores) is the default — good enough for the cleanup stage to work with. Swap base.en → small.en in the URL for meaningfully better raw accuracy at ~2–3× the compute; do that when the recording is long-term important (contract discussions, disputes) or the audio is poor. Non-English: use a multilingual model from the same release tag (e.g., sherpa-onnx-whisper-base).

If a GitHub download fails, verify reachability (`curl -s -o /dev/null -w "%{http_code}" https://objects.githubusercontent.com`) before concluding the route is closed. Only if GitHub itself is blocked should you fall back to asking the user for an externally produced transcript — never claim transcription is impossible without testing.

## Step 2 — Inspect the audio

```bash
ffprobe -v quiet -show_format FILE | grep duration
```

Duration drives everything: compute estimate (duration ÷ 2 with base.en on 2 cores; check nproc), whether to split (step 4), and how to schedule the work honestly with the user.

## Step 3 — Quality gate (do not skip)

Transcribe a 2-minute slice from somewhere mid-recording before committing to the full run:

```bash
python3 scripts/transcribe.py FILE --start 60 --end 180 --out snippet.txt
```

Read the snippet. If it's word salad (wrong language, heavy noise, far-field audio), stop and tell the user what you're seeing — options are the larger model, or asking whether a better recording exists. If it's legible-but-rough, proceed: that's normal, the cleanup stage handles it. The snippet also calibrates the compute estimate (elapsed seconds ÷ 120 = real-time factor).

## Step 4 — Full transcription

scripts/transcribe.py handles any ffmpeg-readable input: converts to 16 kHz mono internally, segments speech with Silero VAD at natural silence boundaries (threshold 0.5, min-silence 0.4 s, max segment 28 s — under Whisper's 30 s decode ceiling), decodes each segment, and writes [MM:SS] text lines with absolute timestamps.

A single tool call times out at 10 minutes, so for recordings over ~15 minutes run it detached and poll:

```bash
nohup python3 scripts/transcribe.py FILE --start 0    --end 1550 --out part1.txt > log1.txt 2>&1 &
nohup python3 scripts/transcribe.py FILE --start 1540             --out part2.txt > log2.txt 2>&1 &
```

Split at roughly the midpoint with a 10-second overlap so no words are lost at the seam; with 2 cores, two processes finish in about the same wall time as one (they share the CPUs) — the split's real purpose is that neither half is lost if one process dies, and on 4+ cores it genuinely halves the time. Poll every ~9 minutes (`ls part*.txt; ps aux | grep transcribe`). The script only writes its output file at the end, so an absent file means still running, not failed — check the log for errors before assuming either.

Merge: compare the lines around the overlap window, drop the duplicated segment(s) from the end of part 1, concatenate.

## Step 5 — Cleanup and deliverables (the judgment half)

Read the entire raw transcript, then produce two markdown files modeled on each other:

**<Name>_Transcript.md** — the cleaned conversation:
- Correct ASR errors using conversation context and everything known about the project — names, products, vendors. (Real examples: "Alice" → Atlas, "Mertina" → Meridian, "Formal" → Formaloo.)
- Attribute speakers from voice-of-content: who talks strategy, who talks implementation, who asks questions. This is inference, not acoustic fact — the pipeline has no diarization.
- The honesty rules, which are the whole point: mark every uncertain reading or attribution with [?]; mark unrecoverable audio [garbled] or [unclear] rather than guessing; reconstructed words go in [brackets]. Garbled audio invites plausible-sounding fabrication — a transcript the user will treat as a record must never contain silently invented content.
- Open with a header note stating the method, the attribution basis, and any coverage gaps (e.g., recording starts mid-meeting — listen for internal evidence like "as we said earlier").
- Organize into numbered topic sections with the [?] convention explained up top.

**<Name>_Notes.md** — secretarial notes with these sections: Meeting summary (one paragraph), Attendees (table with roles), Key topics (numbered), Decisions made, Action items (owner/action/deadline table), Open questions, Notable quotes (only ones clearly heard), Follow-up recommendations for the user. Lead with a coverage caveat if the recording missed part of the meeting.

Deliver both files to the user and save them where their meeting documents live. Close by inviting corrections: the user was in the room and can fix attributions you inferred.

## Known limits (say these, don't hide them)

No speaker diarization — attribution is contextual inference and can be wrong between similar voices. base.en garbles low-volume cross-talk and proper nouns. VAD may swallow sub-quarter-second interjections. The ~200 MB model re-downloads each fresh session (~1 minute). Phone-in-the-room recordings of multi-person meetings are the worst case; a per-speaker mic or platform recording will always beat this pipeline's raw accuracy.
