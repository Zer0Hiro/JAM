# JAM Syntax Guide

Complete reference for the `.jam` music notation language. JAM compiles to Mozzi 2.0 C++ sketches for ESP32/Arduino hardware, with optional WAV preview rendering.

---

## File Format

Files use the `.jam` extension. Lines starting with `#` are comments. Inline comments work too — a `#` preceded by whitespace starts a comment (so `D#3` is a note, not a comment).

Indentation uses spaces (tabs are converted to 4 spaces). Indented blocks define instrument properties, sequence events, pattern beats, loop bodies, and play-together groups.

A `.jam` file is structured in this order (all sections optional):

1. **Global config** — BPM, audio rate, control rate
2. **Instruments** — define synths and drums
3. **Sequences** — note-by-note melodies and bass lines
4. **Patterns** — beat-grid drum/instrument placement
5. **Arrangement** — playback order (sequences, patterns, loops, play-together)

---

## 1. Global Config

Set at the top level. All optional — defaults shown.

```
BPM 120              # tempo in beats per minute (1-300)
AUDIO_RATE 16384     # Mozzi audio sample rate (16384 or 32768)
CONTROL_RATE 64      # Mozzi control loop rate in Hz
KEY C4 MAJOR         # lock notes to C major scale
SWING 30             # swing feel for offbeat 8th notes
HUMANIZE 10          # random timing variation per note
```

| Setting | Default | Valid Values | Description |
|---------|---------|-------------|-------------|
| `BPM` | 120 | 1–300 | Tempo in beats per minute |
| `AUDIO_RATE` | 16384 | 16384, 32768 | Mozzi audio sample rate |
| `CONTROL_RATE` | 64 | positive integer | Mozzi control loop rate in Hz |
| `KEY` | none | `KEY <root> <scale>` | Lock notes to a musical scale (see [Key & Scale](#key--scale)) |
| `SWING` | 0 | 0–100 | Swing amount — delays offbeat 8th notes (50 = triplet feel) |
| `HUMANIZE` | 0 | 0–50 | Random timing offset per note in ms (adds human feel) |

---

## 2. Instruments

Define named instruments with `INSTRUMENT name:` followed by indented properties. There are two types: **SYNTH** (melodic) and **DRUM** (percussive).

### Synth Instrument

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 10 50 200 100
    VOLUME 180
```

### Drum Instrument

```
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255
```

### Instrument Properties

| Property | Required | Values | Description |
|----------|----------|--------|-------------|
| `TYPE` | yes | `SYNTH`, `DRUM` | Melodic synth or drum hit |
| `WAVE` | yes | `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `PLUCK`, `HANDPAN` | Oscillator waveform |
| `ADSR` | no | `attack decay sustain release` (all in ms) | Envelope shape (SYNTH only) |
| `VOLUME` | no | `0`–`255` (default: `200`) | Channel volume |
| `FREQ` | no | integer Hz | Fixed frequency (DRUM only) |
| `DECAY` | no | integer ms | Decay time (DRUM only) |
| `CUTOFF` | no | `20`–`20000` Hz | Low-pass filter cutoff frequency |
| `RESONANCE` | no | `0`–`255` (default: `0`) | Filter resonance / Q factor |
| `REVERB` | no | `0`–`255` (default: `0`) | Reverb wet/dry mix |
| `DELAY` | no | `time_ms feedback` (0–2000, 0–255) | Echo delay time and feedback |
| `GLIDE` | no | `0`–`1000` ms (default: `0`) | Portamento / pitch slide time |
| `PAN` | no | `0`–`255` (default: `127`) | Stereo pan (0=left, 127=center, 255=right) |
| `LFO` | no | `rate depth VOLUME\|PITCH\|CUTOFF\|PAN` | Low Frequency Oscillator (see [LFO](#lfo)) |
| `VOICES` | no | `1`–`4` (default: `1`) | Number of detuned oscillator voices (unison) |
| `DETUNE` | no | `0`–`100` cents (default: `0`) | Detune spread between voices |
| `CHORUS` | no | `0`–`255` (default: `0`) | Chorus effect wet/dry mix |

### Waveforms

| Name | Description |
|------|-------------|
| `SIN` | Sine wave — pure, clean tone |
| `SAW` | Sawtooth — bright, buzzy, good for bass and lead |
| `SQUARE` | Square wave — hollow, retro |
| `TRIANGLE` | Triangle — softer than square, mellow |
| `NOISE` | White noise — percussion, hi-hats, snares |
| `PLUCK` | Karplus-Strong string — guitar, harp, pizzicato |
| `HANDPAN` | Struck metal membrane — additive synthesis (fundamental + octave + octave-fifth + noise transient). SYNTH only. Attack always 1ms, sustain always 0. Default envelope: ADSR 1 600 0 200. Use DECAY to control ring time. |

### LFO

LFO (Low Frequency Oscillator) adds slow modulation to an instrument parameter. Each instrument can have one LFO per target — up to four simultaneous LFOs (VOLUME + PITCH + CUTOFF + PAN).

```
INSTRUMENT wobble_bass:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 2000
    ADSR 5 40 300 120
    VOLUME 200
    LFO 4.0 120 VOLUME     # 4 Hz tremolo, depth 120
    LFO 2.0 30 PITCH       # 2 Hz vibrato, depth 30 cents
    LFO 1.5 800 CUTOFF     # filter sweep ±800 Hz at 1.5 Hz
```

#### LFO syntax

```
LFO <rate> <depth> <target>
```

| Parameter | Range | Description |
|-----------|-------|-------------|
| `rate` | 0.1–20.0 Hz | Oscillation speed (>10 Hz approaches audio range) |
| `depth` | 0–255 | Modulation intensity |
| `target` | `VOLUME`, `PITCH`, `CUTOFF`, or `PAN` | What the LFO modulates |

- **VOLUME LFO** — creates tremolo effect. Depth controls amplitude swing (255 = full 0-to-max)
- **PITCH LFO** — creates vibrato effect. Depth is in cents (100 cents = 1 semitone)
- **CUTOFF LFO** — sweeps the low-pass filter up and down ("wah-wah" / acid bass). Depth is in Hz. Instrument must have `CUTOFF` set
- **PAN LFO** — auto-pans the instrument across the stereo field. Depth is the swing range (0–255). Instrument must have `PAN` set. **ESP32 with I2S DAC only** — will not compile on AVR

### Unison / Detune / Chorus

Stack multiple detuned copies of an oscillator for a thick, wide sound.

```
INSTRUMENT supersaw:
    TYPE SYNTH
    WAVE SAW
    VOICES 3
    DETUNE 20
    CHORUS 80
    ADSR 10 50 200 100
    VOLUME 180
```

| Property | Range | Default | Description |
|----------|-------|---------|-------------|
| `VOICES` | 1–4 | 1 | Number of oscillator copies |
| `DETUNE` | 0–100 | 0 | Spread between voices in cents |
| `CHORUS` | 0–255 | 0 | Short modulated delay for width |

- `VOICES > 2` warns about RAM usage on AVR targets
- `DETUNE > 0` requires `VOICES > 1` (otherwise it's an error)
- `DETUNE > 50` warns about potentially out-of-tune results
- `VOICES` and `DETUNE` have no effect on DRUM instruments

### ADSR Envelope

```
ADSR attack_ms decay_ms sustain_ms release_ms
```

- **Attack** — time to rise from silence to peak
- **Decay** — time to fall from peak to sustain level
- **Sustain** — time held at sustain level
- **Release** — time to fade to silence after note ends

Examples:

| Preset | ADSR | Character |
|--------|------|-----------|
| Fast pluck | `ADSR 2 80 0 60` | Instant attack, quick decay, no sustain |
| Slow pad | `ADSR 300 100 400 500` | Gradual swell, long release |
| General purpose | `ADSR 10 50 200 100` | Balanced all-rounder |

---

## 3. Sequences

Named lists of `PLAY` and `REST` events. Durations are in beats (relative to BPM). Events play one after another (sequentially).

```
SEQUENCE melody:
    PLAY lead C4 0.5      # play instrument "lead", note C4, half a beat
    PLAY lead D#4 0.5     # sharps with #
    PLAY lead E4 1        # one beat
    REST 0.5              # silence for half a beat
    PLAY lead G4 2        # two beats
```

### PLAY syntax

```
PLAY <instrument> <note> <duration> [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
PLAY <instrument> [C4 E4 G4] <duration> [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
```

- **instrument** — must match a defined `INSTRUMENT` name
- **note** — scientific pitch notation (see [Note Names](#note-names))
- **chord** — bracket notation `[note note note]` for polyphonic playback (min 2 notes)
- **duration** — float, in beats relative to BPM (e.g. `0.25` = sixteenth note at 4/4)
- **velocity** — optional, `0`–`255`. Per-note volume scaling. Omit for full instrument volume
- **CUTOFF:value** — optional per-note filter override (20–20000 Hz). Instrument must have `CUTOFF` set. Reverts after the note ends
- **REVERB:value** — optional per-note reverb override (0–255), replaces instrument's reverb for this note
- **DELAY:time:feedback** — optional per-note delay override (time 0–2000ms, feedback 0–255)

For drums without a melodic pitch, omit the note:

```
PLAY kick 1             # drum hit, 1 beat duration
```

### Per-note Effect Overrides

Override an instrument's settings for individual notes:

```
SEQUENCE melody:
    PLAY lead C4 1 200 CUTOFF:800          # darker filter on this note
    PLAY lead E4 1                          # normal instrument settings
    PLAY lead G4 1 180 DELAY:500:120       # longer delay on this note
    PLAY lead C5 1 200 REVERB:180 DELAY:400:100   # multiple overrides
    PLAY lead D5 1 180 CUTOFF:3000 REVERB:200      # bright + wet
```

Overrides require velocity to be specified first. `CUTOFF` override only works on instruments that have `CUTOFF` set — the filter reverts to the instrument's base value after the note ends. `REVERB` and `DELAY` overrides similarly require the corresponding effect configured on the instrument.

### REST syntax

```
REST <duration>
```

Silent pause for the given number of beats.

### VELOCITY_CURVE

Automatically spread velocities across a series of notes — creates crescendo (getting louder) or decrescendo (getting softer) without writing each velocity by hand.

```
VELOCITY_CURVE CRESCENDO <start_vel> <end_vel> <note_count>
VELOCITY_CURVE DECRESCENDO <start_vel> <end_vel> <note_count>
VELOCITY_CURVE OFF
```

| Parameter | Range | Description |
|-----------|-------|-------------|
| `start_vel` | 0–255 | Starting velocity |
| `end_vel` | 0–255 | Ending velocity |
| `note_count` | 1–128 | How many subsequent PLAY notes the curve spans |

The curve linearly interpolates velocity across the next `note_count` PLAY events. After all notes are consumed, velocity returns to normal (full instrument volume).

```
SEQUENCE buildup:
    VELOCITY_CURVE CRESCENDO 40 230 6
    PLAY lead C4 0.5       # vel ~40
    PLAY lead D4 0.5       # vel ~78
    PLAY lead E4 0.5       # vel ~116
    PLAY lead F4 0.5       # vel ~154
    PLAY lead G4 0.5       # vel ~192
    PLAY lead A4 1         # vel ~230

SEQUENCE fadeout:
    VELOCITY_CURVE DECRESCENDO 200 60 4
    PLAY lead G4 1         # vel ~200
    PLAY lead E4 1         # vel ~153
    PLAY lead C4 1         # vel ~107
    PLAY lead C3 2         # vel ~60
```

- VELOCITY_CURVE is **compile-time only** — zero MCU runtime cost. Velocities are baked into the event table
- A note with an explicit velocity override still uses it, but the curve position advances
- `VELOCITY_CURVE OFF` cancels an active curve before it finishes
- REST events do not consume curve positions
- Multiple VELOCITY_CURVEs in the same sequence: each replaces the previous

### Chord example

```
SEQUENCE progression:
    PLAY pad [C4 E4 G4] 2       # C major chord, 2 beats
    PLAY pad [A3 C4 E4] 2       # A minor chord
    PLAY pad [F3 A3 C4] 2       # F major chord
    PLAY pad [G3 B3 D4] 2       # G major chord
```

---

## 4. Patterns

Beat-grid notation for placing instruments at specific positions in a bar. Multiple instruments on the same beat play simultaneously.

```
PATTERN basic_beat:
    BEAT 1: kick        # beat 1 (downbeat)
    BEAT 1: hat         # same beat = simultaneous with kick
    BEAT 1.5: hat       # offbeat (fractional positions OK)
    BEAT 2: snare
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat
```

### BEAT syntax

```
BEAT <position>: <instrument> [note] [duration] [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
BEAT <position>: <instrument> [C4 E4 G4] [duration] [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
```

- **position** — float, 1-based (1 = first beat of bar). Fractional = offbeats (e.g. `1.5`, `2.5`).
- **instrument** — must match a defined `INSTRUMENT`
- **note** — optional pitch for synth instruments in patterns
- **duration** — optional, in beats
- **velocity** — optional, `0`–`255`. Per-hit volume scaling
- **CUTOFF:value** / **REVERB:value** / **DELAY:time:feedback** — optional per-note effect overrides (same as PLAY)
- Default bar length: 4 beats (4/4 time)

### Simultaneous playback in patterns

Place different instruments on the same beat number to play them at the same time:

```
PATTERN band:
    BEAT 1: bass C2     # bass and lead play together on beat 1
    BEAT 1: lead E4
    BEAT 1: kick
    BEAT 2: bass C2
    BEAT 2: lead G4
```

---

## 5. Arrangement

The arrangement section controls playback order. It sits at the top level (no indentation).

### PLAY_SEQUENCE

```
PLAY_SEQUENCE melody
```

Plays the named sequence once, start to finish.

### PLAY_PATTERN

```
PLAY_PATTERN basic_beat
```

Plays one bar of the named pattern.

### LOOP

```
LOOP 4:
    PLAY_SEQUENCE verse
    PLAY_PATTERN drums
```

Repeats the indented body N times. Loops can contain `PLAY_SEQUENCE`, `PLAY_PATTERN`, `PLAY_TOGETHER`, and nested `LOOP` blocks.

```
LOOP 2:
    LOOP 4:
        PLAY_SEQUENCE intro
    PLAY_SEQUENCE chorus
```

### PLAY_TOGETHER

Plays multiple sequences and patterns simultaneously — all children start at the same time and their events are merged onto a single timeline.

```
PLAY_TOGETHER:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
    PLAY_PATTERN drums
```

Without `PLAY_TOGETHER`, arrangement items play one after another:

```
# Sequential — bass plays first, THEN melody, THEN drums
PLAY_SEQUENCE bassline
PLAY_SEQUENCE melody
PLAY_PATTERN drums
```

With `PLAY_TOGETHER`, they play at the same time — like a real band:

```
# Simultaneous — all three play at once
PLAY_TOGETHER:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
    PLAY_PATTERN drums
```

`PLAY_TOGETHER` works inside `LOOP` blocks:

```
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN drums
```

The body can contain `PLAY_SEQUENCE`, `PLAY_PATTERN`, and `LOOP`.

### FADE_IN / FADE_OUT

Gradually ramp master volume up or down over a number of beats:

```
FADE_IN 4                    # fade from silence to full over 4 beats
LOOP 4:
    PLAY_SEQUENCE melody
FADE_OUT 8                   # fade from current volume to silence over 8 beats
LOOP 2:
    PLAY_SEQUENCE outro
```

| Directive | Range | Description |
|-----------|-------|-------------|
| `FADE_IN` | 1–64 beats | Ramp volume from 0 to current master volume |
| `FADE_OUT` | 1–64 beats | Ramp volume from current level to 0 |

Fades are arrangement-level items — they apply to everything that follows until the fade completes. They work inside `LOOP` and `PLAY_TOGETHER` blocks.

### Dynamic BPM / VOLUME Changes

`BPM` and `VOLUME` can appear as arrangement items to change tempo or master volume mid-song:

```
BPM 100
LOOP 2:
    PLAY_SEQUENCE verse
BPM 140
LOOP 2:
    PLAY_SEQUENCE chorus
```

When `BPM` appears after arrangement items have started, it changes the tempo for all subsequent events. When it appears before any arrangement, it sets the initial tempo.

`VOLUME` works the same way — it sets the master volume (0–255) for everything that follows:

```
PLAY_SEQUENCE intro
VOLUME 255
PLAY_SEQUENCE climax
```

---

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

When `KEY` is set, the compiler warns on any `PLAY` note whose pitch class falls outside the scale. This helps catch wrong notes early.

---

## Note Names

Format: `Letter` + optional `Accidental` + `Octave`

| Part | Values | Example |
|------|--------|---------|
| Letter | `A` through `G` (case-insensitive) | `C`, `f` |
| Accidental | `#` or `s` (sharp), `b` (flat), or omit (natural) | `#`, `b` |
| Octave | integer (`-1` to `9`) | `4` |

Examples: `C4` (middle C), `A4` (440 Hz), `D#3`, `Bb2`, `Fs5`, `G7`

### Common Reference

| Note | Frequency |
|------|-----------|
| C2 | 65 Hz |
| C3 | 131 Hz |
| C4 | 262 Hz (middle C) |
| A4 | 440 Hz (tuning standard) |
| C5 | 523 Hz |
| C6 | 1047 Hz |

### Duration Reference (at 120 BPM)

| Duration | Beats | Milliseconds | Musical Name |
|----------|-------|-------------|-------------|
| `4` | 4 beats | 2000 ms | Whole note |
| `2` | 2 beats | 1000 ms | Half note |
| `1` | 1 beat | 500 ms | Quarter note |
| `0.5` | ½ beat | 250 ms | Eighth note |
| `0.25` | ¼ beat | 125 ms | Sixteenth note |

---

## Complete Examples

### Hello World — Single Tone

```
BPM 120

INSTRUMENT tone:
    TYPE SYNTH
    WAVE SIN
    ADSR 10 50 200 100
    VOLUME 200

SEQUENCE melody:
    PLAY tone C4 2
    REST 1
    PLAY tone E4 2
    REST 1
    PLAY tone G4 2

PLAY_SEQUENCE melody
```

### Full Band with PLAY_TOGETHER

```
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    ADSR 5 40 300 120
    VOLUME 220

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    ADSR 10 30 200 100
    VOLUME 180

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 55
    DECAY 100
    VOLUME 255

INSTRUMENT hat:
    TYPE DRUM
    WAVE NOISE
    FREQ 800
    DECAY 30
    VOLUME 140

SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass C2 1
    PLAY bass G2 1
    PLAY bass F2 1

SEQUENCE melody:
    PLAY lead E4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1
    PLAY lead G4 0.5
    PLAY lead E4 0.5
    PLAY lead D4 1

PATTERN beat:
    BEAT 1: kick
    BEAT 1: hat
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: hat

LOOP 2:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN beat
```

### Drum Pattern

```
BPM 110

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255

INSTRUMENT snare:
    TYPE DRUM
    WAVE NOISE
    FREQ 200
    DECAY 60
    VOLUME 220

INSTRUMENT hat:
    TYPE DRUM
    WAVE NOISE
    FREQ 800
    DECAY 30
    VOLUME 140

PATTERN basic_beat:
    BEAT 1: kick
    BEAT 1: hat
    BEAT 2: snare
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat

LOOP 4:
    PLAY_PATTERN basic_beat
```

### Chord Progression

```
BPM 100

INSTRUMENT pad:
    TYPE SYNTH
    WAVE SAW
    ADSR 50 100 300 200
    VOLUME 180

SEQUENCE progression:
    PLAY pad [C4 E4 G4] 2
    PLAY pad [A3 C4 E4] 2
    PLAY pad [F3 A3 C4] 2
    PLAY pad [G3 B3 D4] 2

LOOP 2:
    PLAY_SEQUENCE progression
```

### Effects and Panning

```
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 600
    RESONANCE 100
    PAN 100
    ADSR 5 40 300 120
    VOLUME 220

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    GLIDE 100
    DELAY 300 150
    REVERB 120
    PAN 180
    ADSR 10 30 200 100
    VOLUME 180

SEQUENCE melody:
    PLAY lead C4 0.5 200
    PLAY lead E4 0.5 160
    PLAY lead G4 1 220

SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass G2 1

LOOP 2:
    PLAY_TOGETHER:
        PLAY_SEQUENCE melody
        PLAY_SEQUENCE bassline
```

### Envelope Shaping (Pad + Pluck)

```
BPM 90

INSTRUMENT pad:
    TYPE SYNTH
    WAVE SIN
    ADSR 300 100 400 500
    VOLUME 160

INSTRUMENT pluck:
    TYPE SYNTH
    WAVE SAW
    ADSR 2 80 0 60
    VOLUME 200

SEQUENCE pad_chords:
    PLAY pad C4 4
    PLAY pad E4 4
    PLAY pad G4 4
    PLAY pad C5 4

SEQUENCE pluck_line:
    PLAY pluck C5 0.25
    REST 0.25
    PLAY pluck E5 0.25
    REST 0.25
    PLAY pluck G5 0.25
    REST 0.25
    PLAY pluck C6 0.25
    REST 0.25

PLAY_SEQUENCE pad_chords
LOOP 4:
    PLAY_SEQUENCE pluck_line
```

---

## Validation & Warnings

The compiler runs semantic analysis after parsing and reports errors and warnings.

### Errors (compilation stops)

| Check | Description |
|-------|-------------|
| Undefined instrument | `PLAY` / `BEAT` references an instrument not defined |
| Undefined sequence | `PLAY_SEQUENCE` references a sequence not defined |
| Undefined pattern | `PLAY_PATTERN` references a pattern not defined |
| Invalid note name | Note doesn't match `[A-G][#sb]?[0-9]` pattern |
| Negative duration | Beat duration <= 0 |
| Volume out of range | Volume not 0–255 |
| Velocity out of range | Velocity not 0–255 |
| Negative ADSR | Any ADSR parameter < 0 |
| LOOP count <= 0 | Loop must repeat at least once |
| Cutoff out of range | CUTOFF not 20–20000 |
| Resonance out of range | RESONANCE not 0–255 |
| Reverb out of range | REVERB not 0–255 |
| Delay time out of range | DELAY time not 0–2000 |
| Delay feedback out of range | DELAY feedback not 0–255 |
| Pan out of range | PAN not 0–255 |
| BPM change out of range | Dynamic BPM not 1–300 |
| SWING out of range | SWING not 0–100 |
| HUMANIZE out of range | HUMANIZE not 0–50 |
| FADE duration invalid | FADE_IN / FADE_OUT not 1–64 beats |
| PLUCK on DRUM | PLUCK wave cannot be used with DRUM instruments |
| LFO rate out of range | LFO rate not 0.1–20.0 |
| LFO depth out of range | LFO depth not 0–255 |
| VOICES out of range | VOICES not 1–4 |
| DETUNE out of range | DETUNE not 0–100 |
| CHORUS out of range | CHORUS not 0–255 |
| DETUNE without VOICES | DETUNE > 0 requires VOICES > 1 |
| Per-note REVERB out of range | REVERB override not 0–255 |
| Per-note DELAY time out of range | DELAY time override not 0–2000 |
| Per-note DELAY feedback out of range | DELAY feedback override not 0–255 |
| Per-note CUTOFF out of range | CUTOFF override not 20–20000 |
| VELOCITY_CURVE velocity out of range | Start or end velocity not 0–255 |
| VELOCITY_CURVE note_count out of range | Note count not 1–128 |

### Warnings (compilation continues)

| Check | Description |
|-------|-------------|
| Very short ADSR | ADSR < 5 ms (control rate is ~16 ms/step) |
| Note outside piano range | MIDI < 21 or > 108 |
| Too many synths | > 4 synths (ATmega328 has 2 KB RAM) |
| Fast BPM | BPM > 300 may exceed AVR timing |
| Non-standard audio rate | Not 16384 or 32768 |
| Beat outside bar | Beat position > bar length |
| PLAY_TOGETHER < 2 items | Use PLAY_SEQUENCE / PLAY_PATTERN directly |
| GLIDE on DRUM | Portamento has no effect on drum instruments |
| GLIDE > 1000 | Very long glide may sound unnatural |
| GLIDE on PLUCK | Portamento doesn't apply well to plucked strings |
| LFO rate > 10 | LFO rate approaches audio range |
| LFO VOLUME on DRUM | Volume LFO on drum has limited effect |
| LFO PITCH on DRUM | Pitch LFO has no effect on drums |
| LFO CUTOFF on DRUM | Cutoff LFO on drum has limited effect |
| LFO PAN on DRUM | Pan LFO on drum has limited effect |
| LFO PAN (AVR target) | LFO PAN requires ESP32 with I2S DAC — won't compile on AVR |
| Per-note CUTOFF without instrument CUTOFF | Override has no effect if instrument lacks CUTOFF |
| VELOCITY_CURVE extends beyond sequence | Note count exceeds remaining PLAY events in sequence |
| >2 CUTOFF LFOs (AVR) | Multiple filter LFOs may exceed AVR RAM budget |
| VOICES > 2 | Uses significant RAM on AVR targets |
| VOICES on DRUM | Unison voices have no effect on drums |
| DETUNE > 50 | Large detune may sound out of tune |
| Note outside KEY | Note pitch class not in declared scale |
| High SWING | SWING > 75 is extreme, may sound unmusical |
| High HUMANIZE | HUMANIZE > 30 creates very loose timing |

---

## Grammar Summary

```
program        := (config | instrument | sequence | pattern | arrangement)* EOF

config         := ("BPM" | "AUDIO_RATE" | "CONTROL_RATE") NUMBER
                 | "KEY" NOTE ("MAJOR"|"MINOR"|"DORIAN"|"PHRYGIAN"|"LYDIAN"|"MIXOLYDIAN"|"PENTATONIC"|"BLUES")
                 | "SWING" NUMBER
                 | "HUMANIZE" NUMBER

instrument     := "INSTRUMENT" IDENT ":"
                      ("TYPE" ("SYNTH" | "DRUM")
                     | "WAVE" ("SIN" | "SAW" | "SQUARE" | "TRIANGLE" | "NOISE" | "PLUCK" | "HANDPAN")
                     | "ADSR" NUMBER NUMBER NUMBER NUMBER
                     | "VOLUME" NUMBER
                     | "FREQ" NUMBER
                     | "DECAY" NUMBER
                     | "CUTOFF" NUMBER
                     | "RESONANCE" NUMBER
                     | "REVERB" NUMBER
                     | "DELAY" NUMBER NUMBER
                     | "GLIDE" NUMBER
                     | "PAN" NUMBER
                     | "LFO" NUMBER NUMBER ("VOLUME" | "PITCH" | "CUTOFF" | "PAN")
                     | "VOICES" NUMBER
                     | "DETUNE" NUMBER
                     | "CHORUS" NUMBER)+

sequence       := "SEQUENCE" IDENT ":"
                      ("PLAY" IDENT NOTE NUMBER [NUMBER] [fx_override]*
                     | "PLAY" IDENT "[" NOTE+ "]" NUMBER [NUMBER] [fx_override]*
                     | "REST" NUMBER
                     | velocity_curve)+

velocity_curve := "VELOCITY_CURVE" ("CRESCENDO" | "DECRESCENDO") NUMBER NUMBER NUMBER
                | "VELOCITY_CURVE" "OFF"

fx_override    := "CUTOFF" ":" NUMBER
                | "REVERB" ":" NUMBER
                | "DELAY" ":" NUMBER ":" NUMBER

pattern        := "PATTERN" IDENT ":"
                      ("BEAT" NUMBER ":" IDENT [NOTE] [NUMBER] [NUMBER] [fx_override]*)+

arrangement    := (loop | play_seq | play_pat | play_together | bpm_change | vol_change | fade)+
bpm_change     := "BPM" NUMBER
vol_change     := "VOLUME" NUMBER
fade           := ("FADE_IN" | "FADE_OUT") NUMBER
loop           := "LOOP" NUMBER ":" INDENT arrangement DEDENT
play_seq       := "PLAY_SEQUENCE" IDENT
play_pat       := "PLAY_PATTERN" IDENT
play_together  := "PLAY_TOGETHER" ":" INDENT arrangement DEDENT
```

### Keywords

All keywords must be UPPERCASE:

`BPM`, `AUDIO_RATE`, `CONTROL_RATE`, `KEY`, `SWING`, `HUMANIZE`, `MAJOR`, `MINOR`, `DORIAN`, `PHRYGIAN`, `LYDIAN`, `MIXOLYDIAN`, `PENTATONIC`, `BLUES`, `INSTRUMENT`, `TYPE`, `SYNTH`, `DRUM`, `WAVE`, `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `PLUCK`, `HANDPAN`, `ADSR`, `VOLUME`, `FREQ`, `DECAY`, `CUTOFF`, `RESONANCE`, `REVERB`, `DELAY`, `GLIDE`, `PAN`, `LFO`, `PITCH`, `VOICES`, `DETUNE`, `CHORUS`, `SEQUENCE`, `PATTERN`, `PLAY`, `REST`, `BEAT`, `LOOP`, `PLAY_SEQUENCE`, `PLAY_PATTERN`, `PLAY_TOGETHER`, `FADE_IN`, `FADE_OUT`, `VELOCITY_CURVE`, `CRESCENDO`, `DECRESCENDO`, `OFF`

### Identifiers

Lowercase names for instruments, sequences, and patterns. Can contain letters, digits, and underscores.

### Notes

`C4`, `D#3`, `Bb2`, `Fs5` — case-insensitive letter, optional accidental (`#`, `s`, `b`), octave number.

### Numbers

Integers or floats: `120`, `0.5`, `16384`.

---

## Hardware Targets

| Board | Platform | Audio Output | Stereo |
|-------|----------|-------------|--------|
| ESP32 (esp32dev) | pioarduino | Internal DAC (GPIO 25) or I2S DAC | Yes (I2S DAC) |
| Arduino Uno | ATmega328P | PWM output on pin 9 | No (mono only) |

Configuration is in `platformio.ini`. ESP32 is the primary target.

**Stereo features** (`PAN`, `LFO PAN`) require ESP32 with an I2S DAC. When any instrument uses `LFO PAN`, the compiler emits `MOZZI_STEREO` and `MOZZI_OUTPUT_I2S_DAC` config macros and guards with `#ifdef __AVR__ #error`.
