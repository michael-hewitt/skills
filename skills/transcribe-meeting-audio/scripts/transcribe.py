#!/usr/bin/env python3
"""Transcribe long-form meeting audio with sherpa-onnx Whisper + Silero VAD.

Usage:
  python3 transcribe.py AUDIO_FILE [--model MODEL_DIR] [--out OUT.txt]
                        [--start SECONDS] [--end SECONDS] [--vad VAD_PATH]

AUDIO_FILE may be any format ffmpeg reads (m4a, mp3, wav, mp4...).
--start/--end transcribe only a slice (use for the 2-minute quality gate).
Timestamps in the output are absolute to the original file.

Prereqs (see SKILL.md for download URLs):
  pip install sherpa-onnx numpy
  ffmpeg on PATH
  MODEL_DIR containing <prefix>-encoder.int8.onnx, <prefix>-decoder.int8.onnx,
  <prefix>-tokens.txt (as shipped in sherpa-onnx whisper release tarballs)
  silero_vad.onnx
"""
import argparse, glob, os, subprocess, sys, tempfile, time, wave

import numpy as np
import sherpa_onnx


def find_model_files(model_dir):
    enc = sorted(glob.glob(os.path.join(model_dir, "*encoder.int8.onnx")))
    dec = sorted(glob.glob(os.path.join(model_dir, "*decoder.int8.onnx")))
    tok = sorted(glob.glob(os.path.join(model_dir, "*tokens.txt")))
    if not (enc and dec and tok):
        sys.exit(f"model files not found in {model_dir}")
    return enc[0], dec[0], tok[0]


def load_audio(path, start, end):
    """Convert any input to 16 kHz mono PCM via ffmpeg and return float32 samples."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    cmd = ["ffmpeg", "-y", "-v", "quiet", "-i", path]
    if start:
        cmd += ["-ss", str(start)]
    if end:
        cmd += ["-to", str(end)]
    cmd += ["-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path]
    subprocess.run(cmd, check=True)
    with wave.open(wav_path) as f:
        sr = f.getframerate()
        audio = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)
        audio = audio.astype(np.float32) / 32768.0
    os.unlink(wav_path)
    return sr, audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default="sherpa-onnx-whisper-base.en")
    ap.add_argument("--vad", default="silero_vad.onnx")
    ap.add_argument("--out", default="transcript_raw.txt")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    enc, dec, tok = find_model_files(args.model)
    sr, audio = load_audio(args.audio, args.start, args.end)
    offset = args.start

    recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=enc, decoder=dec, tokens=tok, num_threads=args.threads,
    )

    vc = sherpa_onnx.VadModelConfig()
    vc.silero_vad.model = args.vad
    vc.silero_vad.threshold = 0.5            # speech probability gate
    vc.silero_vad.min_silence_duration = 0.4  # close segment after 0.4s silence
    vc.silero_vad.min_speech_duration = 0.25  # ignore blips shorter than this
    vc.silero_vad.max_speech_duration = 28.0  # stay under Whisper's 30s ceiling
    vc.sample_rate = sr
    vad = sherpa_onnx.VoiceActivityDetector(vc, buffer_size_in_seconds=120)

    def decode(seg):
        s = recognizer.create_stream()
        s.accept_waveform(sr, seg.samples)
        recognizer.decode_stream(s)
        return seg.start / sr + offset, s.result.text.strip()

    results, window, i, t0 = [], 512, 0, time.time()
    while i < len(audio):
        chunk = audio[i:i + window]
        if len(chunk) < window:
            chunk = np.pad(chunk, (0, window - len(chunk)))
        vad.accept_waveform(chunk)
        i += window
        while not vad.empty():
            ts, text = decode(vad.front)
            if text:
                results.append((ts, text))
            vad.pop()
    vad.flush()
    while not vad.empty():
        ts, text = decode(vad.front)
        if text:
            results.append((ts, text))
        vad.pop()

    with open(args.out, "w") as f:
        for ts, text in results:
            m, s = divmod(int(ts), 60)
            h, m = divmod(m, 60)
            stamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            f.write(f"[{stamp}] {text}\n")
    print(f"segments: {len(results)}  elapsed: {time.time()-t0:.0f}s  -> {args.out}")


if __name__ == "__main__":
    main()
