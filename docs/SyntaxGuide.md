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
```

| Setting | Default | Valid Values | Description |
|---------|---------|-------------|-------------|
| `BPM` | 120 | 1–300 | Tempo in beats per minute |
| `AUDIO_RATE` | 16384 | 16384, 32768 | Mozzi audio sample rate |
| `CONTROL_RATE` | 64 | positive integer | Mozzi control loop rate in Hz |

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
| `WAVE` | yes | `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE` | Oscillator waveform |
| `ADSR` | no | `attack decay sustain release` (all in ms) | Envelope shape (SYNTH only) |
| `VOLUME` | no | `0`–`255` (default: `200`) | Channel volume |
| `FREQ` | no | integer Hz | Fixed frequency (DRUM only) |
| `DECAY` | no | integer ms | Decay time (DRUM only) |

### Waveforms

| Name | Description |
|------|-------------|
| `SIN` | Sine wave — pure, clean tone |
| `SAW` | Sawtooth — bright, buzzy, good for bass and lead |
| `SQUARE` | Square wave — hollow, retro |
| `TRIANGLE` | Triangle — softer than square, mellow |
| `NOISE` | White noise — percussion, hi-hats, snares |

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
PLAY <instrument> <note> <duration>
PLAY <instrument> [C4 E4 G4] <duration>     # chord (multiple notes)
```

- **instrument** — must match a defined `INSTRUMENT` name
- **note** — scientific pitch notation (see [Note Names](#note-names))
- **chord** — bracket notation `[note note note]` for polyphonic playback (min 2 notes)
- **duration** — float, in beats relative to BPM (e.g. `0.25` = sixteenth note at 4/4)

For drums without a melodic pitch, omit the note:

```
PLAY kick 1             # drum hit, 1 beat duration
```

### REST syntax

```
REST <duration>
```

Silent pause for the given number of beats.

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
BEAT <position>: <instrument>
BEAT <position>: <instrument> <note>
BEAT <position>: <instrument> [C4 E4 G4]
```

- **position** — float, 1-based (1 = first beat of bar). Fractional = offbeats (e.g. `1.5`, `2.5`).
- **instrument** — must match a defined `INSTRUMENT`
- **note** — optional pitch for synth instruments in patterns
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
| Negative ADSR | Any ADSR parameter < 0 |
| LOOP count <= 0 | Loop must repeat at least once |

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

---

## Grammar Summary

```
program        := (config | instrument | sequence | pattern | arrangement)* EOF

config         := ("BPM" | "AUDIO_RATE" | "CONTROL_RATE") NUMBER

instrument     := "INSTRUMENT" IDENT ":"
                      ("TYPE" ("SYNTH" | "DRUM")
                     | "WAVE" ("SIN" | "SAW" | "SQUARE" | "TRIANGLE" | "NOISE")
                     | "ADSR" NUMBER NUMBER NUMBER NUMBER
                     | "VOLUME" NUMBER
                     | "FREQ" NUMBER
                     | "DECAY" NUMBER)+

sequence       := "SEQUENCE" IDENT ":"
                      ("PLAY" IDENT NOTE NUMBER
                     | "PLAY" IDENT "[" NOTE+ "]" NUMBER
                     | "REST" NUMBER)+

pattern        := "PATTERN" IDENT ":"
                      ("BEAT" NUMBER ":" IDENT [NOTE] [NUMBER])+

arrangement    := (loop | play_seq | play_pat | play_together)+
loop           := "LOOP" NUMBER ":" INDENT arrangement DEDENT
play_seq       := "PLAY_SEQUENCE" IDENT
play_pat       := "PLAY_PATTERN" IDENT
play_together  := "PLAY_TOGETHER" ":" INDENT arrangement DEDENT
```

### Keywords

All keywords must be UPPERCASE:

`BPM`, `AUDIO_RATE`, `CONTROL_RATE`, `INSTRUMENT`, `TYPE`, `SYNTH`, `DRUM`, `WAVE`, `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `ADSR`, `VOLUME`, `FREQ`, `DECAY`, `SEQUENCE`, `PATTERN`, `PLAY`, `REST`, `BEAT`, `LOOP`, `PLAY_SEQUENCE`, `PLAY_PATTERN`, `PLAY_TOGETHER`

### Identifiers

Lowercase names for instruments, sequences, and patterns. Can contain letters, digits, and underscores.

### Notes

`C4`, `D#3`, `Bb2`, `Fs5` — case-insensitive letter, optional accidental (`#`, `s`, `b`), octave number.

### Numbers

Integers or floats: `120`, `0.5`, `16384`.

---

## Hardware Targets

| Board | Platform | Audio Output |
|-------|----------|-------------|
| ESP32 (esp32dev) | pioarduino | Internal DAC (GPIO 25) or configurable PWM pin |
| Arduino Uno | ATmega328P | PWM output on pin 9 |

Configuration is in `platformio.ini`. ESP32 is the primary target.
