---
sidebar_position: 1
---

# Global Config

Set at the top level of a `.jam` file. All optional — defaults shown.

```
BPM 120              # tempo in beats per minute (1-300)
AUDIO_RATE 16384     # Mozzi audio sample rate (16384 or 32768)
CONTROL_RATE 64      # Mozzi control loop rate in Hz
KEY C4 MAJOR         # lock notes to C major scale
SWING 30             # swing feel for offbeat 8th notes
HUMANIZE 10          # random timing variation per note
```

## Settings Reference

| Setting | Default | Valid Values | Description |
|---------|---------|-------------|-------------|
| `BPM` | 120 | 1–300 | Tempo in beats per minute |
| `AUDIO_RATE` | 16384 | 16384, 32768 | Mozzi audio sample rate |
| `CONTROL_RATE` | 64 | positive integer | Mozzi control loop rate in Hz |
| `KEY` | none | `KEY <root> <scale>` | Lock notes to a musical scale |
| `SWING` | 0 | 0–100 | Swing amount — delays offbeat 8th notes (50 = triplet feel) |
| `HUMANIZE` | 0 | 0–50 | Random timing offset per note in ms (adds human feel) |

## Key & Scale

Lock your composition to a musical scale with `KEY`. Notes outside the declared scale trigger a warning during compilation.

```
KEY C4 MAJOR          # C major scale
KEY A3 MINOR          # A natural minor
KEY D4 PENTATONIC     # D pentatonic
KEY E4 BLUES          # E blues scale
```

### Syntax

```
KEY <root_note> <scale_type>
```

- **root_note** — any note (C4, D#3, etc.). The octave sets the reference; the pitch class defines the key.
- **scale_type** — one of: `MAJOR`, `MINOR`, `DORIAN`, `PHRYGIAN`, `LYDIAN`, `MIXOLYDIAN`, `PENTATONIC`, `BLUES`

### Available Scales

| Scale | Intervals (semitones) | Character |
|-------|----------------------|-----------|
| `MAJOR` | 0, 2, 4, 5, 7, 9, 11 | Happy, bright |
| `MINOR` | 0, 2, 3, 5, 7, 8, 10 | Sad, dark |
| `DORIAN` | 0, 2, 3, 5, 7, 9, 10 | Jazzy minor |
| `PHRYGIAN` | 0, 1, 3, 5, 7, 8, 10 | Spanish, exotic |
| `LYDIAN` | 0, 2, 4, 6, 7, 9, 11 | Dreamy, bright |
| `MIXOLYDIAN` | 0, 2, 4, 5, 7, 9, 10 | Bluesy major |
| `PENTATONIC` | 0, 2, 4, 7, 9 | Simple, universal |
| `BLUES` | 0, 3, 5, 6, 7, 10 | Bluesy, soulful |

When `KEY` is set, the compiler warns on any `PLAY` note whose pitch class falls outside the scale.
