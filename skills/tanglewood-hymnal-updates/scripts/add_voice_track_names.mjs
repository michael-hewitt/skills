#!/usr/bin/env node
// Normalize author-provided MIDI files (e.g. Tanglewood Hymnal LilyPond exports) so that every
// note-carrying track has a voice trackName event that Sing Your Part recognizes.
//
// The webapp identifies voice tracks by trackName (Soprano/Alto/Tenor/Bass/Piano) and falls back
// to the legacy channel mapping (0=soprano, 1=alto, 2=tenor, 3=bass, 4=piano) for tracks without
// a recognized name. Author-provided files typically rely on that fallback; this script makes
// them self-describing by deriving each note track's name from its channel:
//   - a note-carrying track with no trackName gets one inserted (deltaTime 0, at track start)
//   - a note-carrying track with an unrecognized trackName (e.g. ':soprano') has it replaced
//   - tracks without notes (title/conductor tracks, empty staves) are left untouched
//   - all note, meta, and timing bytes are preserved exactly
//
// Each file is verified in memory before writing: the note events (absolute tick, channel, note,
// velocity) and tempo/key/time-signature metas of the rewritten file must match the original
// exactly, and every note track must end up named for its channel voice. Files that cannot be
// safely normalized (a track with notes on multiple channels, channels above 4, parse failures)
// are skipped with an error and left unmodified.
//
// Usage:
//   node add_voice_track_names.mjs [--dry-run] <file.mid | directory> [...more]
//
// Directories are scanned recursively for *.mid files. Requires the 'midi-file' npm package,
// resolved from the webapp repo (a sibling of the hymnals repo) or the current directory.

import fs from 'fs';
import os from 'os';
import path from 'path';
import { createRequire } from 'module';

const require = createRequire(import.meta.url);

function resolveMidiFilePackage() {
  const candidates = [
    process.cwd(),
    path.join(os.homedir(), 'dev/crescendo/webapp/server'),
    path.join(os.homedir(), 'dev/crescendo/webapp'),
  ];
  for (const dir of candidates) {
    try {
      return require(require.resolve('midi-file', { paths: [dir] }));
    } catch {
      // try the next candidate
    }
  }
  console.error("Cannot find the 'midi-file' npm package (looked in cwd and ~/dev/crescendo/webapp).");
  console.error('Run from the webapp repo, or npm install midi-file somewhere on the search path.');
  process.exit(1);
}

const { parseMidi, writeMidi } = resolveMidiFilePackage();

const channelVoiceNames = ['Soprano', 'Alto', 'Tenor', 'Bass', 'Piano'];

// Lowercased track names the webapp's Voice enum recognizes (common/src/model.ts). Only names a
// note track might legitimately carry are listed; anything else is replaced from the channel.
const recognizedVoiceNames = new Set([
  'descant', 'melody', 'melody-1', 'melody-2', 'cantor', 'treble',
  'soprano-solo', 'soprano-1', 'soprano-2', 'soprano', 'mezzo',
  'alto-solo', 'alto-1', 'alto-2', 'alto', 'contralto',
  'tenor-solo', 'tenor-1', 'tenor-2', 'tenor', 'baritone',
  'bass-solo', 'bass-1', 'bass-2', 'bass', 'counter-tenor',
  'vocal', 'group-1', 'group-2', 'group-3', 'group-4', 'piano',
]);

function collectMidFiles(target) {
  const stat = fs.statSync(target);
  if (stat.isFile()) {
    return target.endsWith('.mid') ? [target] : [];
  }
  return fs
    .readdirSync(target, { withFileTypes: true, recursive: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.mid'))
    .map((entry) => path.join(entry.parentPath ?? entry.path, entry.name));
}

// Flatten note events (with absolute ticks) and timing metas for before/after comparison
function fingerprint(midi) {
  const notes = [];
  const metas = [];
  for (const track of midi.tracks) {
    let tick = 0;
    for (const event of track) {
      tick += event.deltaTime;
      if (event.type === 'noteOn' || event.type === 'noteOff') {
        notes.push(`${tick}|${event.type}|${event.channel}|${event.noteNumber}|${event.velocity}`);
      } else if (['setTempo', 'timeSignature', 'keySignature', 'smpteOffset'].includes(event.type)) {
        const { deltaTime: _deltaTime, ...rest } = event;
        metas.push(`${tick}|${JSON.stringify(rest, Object.keys(rest).sort())}`);
      }
    }
  }
  return JSON.stringify({ notes: notes.sort(), metas: metas.sort() });
}

function normalizeTracks(midi, file) {
  let changed = false;
  const tracks = midi.tracks.map((track, trackIndex) => {
    const noteChannels = [...new Set(track.filter((e) => e.type === 'noteOn').map((e) => e.channel))];
    if (noteChannels.length === 0) {
      return track; // title/conductor track or empty staff -- leave untouched
    }
    if (noteChannels.length > 1) {
      throw new Error(`track ${trackIndex} has notes on multiple channels (${noteChannels}); split it first`);
    }
    if (noteChannels[0] >= channelVoiceNames.length) {
      throw new Error(`track ${trackIndex} uses unmapped channel ${noteChannels[0]}`);
    }
    const voiceName = channelVoiceNames[noteChannels[0]];
    const nameEvent = track.find((e) => e.type === 'trackName');
    if (!nameEvent) {
      changed = true;
      return [{ type: 'trackName', deltaTime: 0, text: voiceName }, ...track];
    }
    if (recognizedVoiceNames.has(nameEvent.text?.trim().toLowerCase())) {
      return track; // already carries a recognized voice name
    }
    changed = true;
    console.log(`  replacing unrecognized track name '${nameEvent.text}' with '${voiceName}' in ${path.basename(file)}`);
    return track.map((e) => (e === nameEvent ? { ...e, text: voiceName } : e));
  });
  return { tracks, changed };
}

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const targets = args.filter((a) => a !== '--dry-run');
if (targets.length === 0) {
  console.error('Usage: node add_voice_track_names.mjs [--dry-run] <file.mid | directory> [...more]');
  process.exit(1);
}

const files = targets.flatMap(collectMidFiles);
let rewritten = 0;
let unchanged = 0;
let failed = 0;
for (const file of files) {
  try {
    const originalBytes = fs.readFileSync(file);
    const midi = parseMidi(originalBytes);
    const { tracks, changed } = normalizeTracks(midi, file);
    if (!changed) {
      unchanged++;
      continue;
    }
    const newMidi = { header: midi.header, tracks };
    const newBytes = new Uint8Array(writeMidi(newMidi));
    const reparsed = parseMidi(newBytes);
    if (fingerprint(reparsed) !== fingerprint(midi)) {
      throw new Error('verification failed: rewritten file is not note/meta equivalent to the original');
    }
    for (const [trackIndex, track] of reparsed.tracks.entries()) {
      const noteOn = track.find((e) => e.type === 'noteOn');
      if (!noteOn) {
        continue;
      }
      const name = track.find((e) => e.type === 'trackName')?.text?.trim().toLowerCase();
      if (!name || !recognizedVoiceNames.has(name)) {
        throw new Error(`verification failed: note track ${trackIndex} still lacks a recognized voice name`);
      }
    }
    if (!dryRun) {
      fs.writeFileSync(file, newBytes);
    }
    rewritten++;
  } catch (error) {
    failed++;
    console.error(`SKIP ${file}: ${error.message}`);
  }
}
console.log(
  `${dryRun ? '[dry-run] ' : ''}${rewritten} rewritten, ${unchanged} already normalized, ${failed} skipped ` +
    `(of ${files.length} .mid files)`,
);
process.exit(failed > 0 ? 1 : 0);
