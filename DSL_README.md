# Mozzi DSL Reference

A Python DSL that compiles human-readable music notation into Mozzi 2.0 C++ sketches for Arduino Uno, or renders directly to WAV for preview.

## Quick Start

```bash
# Generate Mozzi C++ to stdout
python3 -m dsl.compiler my_song.jam

# Generate C++ to file
python3 -m dsl.compiler my_song.jam -o src/main.cpp

# Render WAV audio preview (no Arduino needed)
python3 -m dsl.compiler my_song.jam --wav -o my_song.wav

# Parse only (validate syntax, show AST)
python3 -m dsl.compiler my_song.jam --dry-run --verbose
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `-o PATH` | Output file path (omit for stdout in C++ mode) |
| `--wav` | Render to WAV instead of C++ |
| `--verbose`, `-v` | Print AST and diagnostics |
| `--dry-run` | Parse and validate only, no output generated |

---

## File Format

Files use the `.jam` extension. Lines starting with `#` are comments. Inline comments work too — a `#` preceded by whitespace starts a comment (so `D#3` is a note, not a comment).

Indentation uses spaces (tabs converted to 4 spaces). Indented blocks define instrument properties, sequence events, pattern beats, and loop bodies.

---

## Syntax Reference

### 1. Global Config

Set at the top level. All optional — defaults shown.

```
BPM 120              # tempo in beats per minute (1-300)
AUDIO_RATE 16384     # Mozzi audio sample rate (16384 or 32768)
CONTROL_RATE 64      # Mozzi control loop rate in Hz
```

### 2. Instruments

Define named instruments with `INSTRUMENT name:` followed by indented properties.

#### Synth Instrument

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 10 50 200 100
    VOLUME 180
```

#### Drum Instrument

```
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255
```

#### Instrument Properties

| Property | Required | Values | Description |
|----------|----------|--------|-------------|
| `TYPE` | yes | `SYNTH`, `DRUM` | Melodic synth or drum hit |
| `WAVE` | yes | `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE` | Oscillator waveform |
| `ADSR` | no | `attack decay sustain release` (all in ms) | Envelope shape (SYNTH only) |
| `VOLUME` | no | `0`-`255` (default: `200`) | Channel volume |
| `FREQ` | no | integer Hz | Fixed frequency (DRUM only) |
| `DECAY` | no | integer ms | Decay time (DRUM only) |

#### Waveforms

| Name | Description |
|------|-------------|
| `SIN` | Sine wave — pure, clean tone |
| `SAW` | Sawtooth — bright, buzzy, good for bass/lead |
| `SQUARE` | Square wave — hollow, retro |
| `TRIANGLE` | Triangle — softer than square, mellow |
| `NOISE` | White noise — percussion, hi-hats, snares |

#### ADSR Envelope

```
ADSR attack_ms decay_ms sustain_ms release_ms
```

- **Attack**: time to rise from silence to peak (ms)
- **Decay**: time to fall from peak to sustain level (ms)
- **Sustain**: time held at sustain level (ms)
- **Release**: time to fade to silence after note ends (ms)

Examples:
- `ADSR 2 80 0 60` — fast pluck (instant attack, quick decay, no sustain)
- `ADSR 300 100 400 500` — slow pad (gradual swell, long release)
- `ADSR 10 50 200 100` — general purpose

### 3. Sequences

Named lists of `PLAY` and `REST` events. Durations are in beats (relative to BPM).

```
SEQUENCE melody:
    PLAY lead C4 0.5      # play instrument "lead", note C4, half a beat
    PLAY lead D#4 0.5     # sharps with #
    PLAY lead E4 1        # one beat
    REST 0.5              # silence for half a beat
    PLAY lead G4 2        # two beats
```

#### PLAY syntax

```
PLAY <instrument_name> <note> <duration_beats>
```

- **instrument_name**: must match a defined `INSTRUMENT`
- **note**: scientific pitch notation (see Note Names below)
- **duration_beats**: float, relative to BPM (e.g. `0.25` = sixteenth note at 4/4)

#### REST syntax

```
REST <duration_beats>
```

Silent pause for the given number of beats.

#### Note Names

Format: `Letter` + optional `Accidental` + `Octave`

| Part | Values | Example |
|------|--------|---------|
| Letter | `A` through `G` (case-insensitive) | `C`, `f` |
| Accidental | `#` or `s` (sharp), `b` (flat), or omit (natural) | `#`, `b` |
| Octave | integer (`-1` to `9`) | `4` |

Examples: `C4` (middle C), `A4` (440Hz), `D#3`, `Bb2`, `Fs5`, `G7`

Common reference:

| Note | Frequency |
|------|-----------|
| C2 | 65 Hz |
| C3 | 131 Hz |
| C4 | 262 Hz (middle C) |
| A4 | 440 Hz (tuning standard) |
| C5 | 523 Hz |
| C6 | 1047 Hz |

### 4. Patterns

Drum patterns define which instruments trigger at which beat position within a bar.

```
PATTERN basic_beat:
    BEAT 1: kick        # beat 1 (downbeat)
    BEAT 1: hat         # multiple instruments on same beat
    BEAT 1.5: hat       # offbeat (fractional positions OK)
    BEAT 2: snare
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat
```

#### BEAT syntax

```
BEAT <position>: <instrument_name>
```

- **position**: float, 1-based (1 = first beat of bar). Fractional = offbeats.
- **instrument_name**: must match a defined `INSTRUMENT`
- Default bar length: 4 beats (4/4 time)

### 5. Arrangement

The arrangement section controls playback order. It sits at the top level (no indentation).

#### Play a sequence

```
PLAY_SEQUENCE melody
```

Plays the named sequence once, start to finish.

#### Play a pattern

```
PLAY_PATTERN basic_beat
```

Plays one bar of the named drum pattern.

#### Loop

```
LOOP 4:
    PLAY_SEQUENCE verse
    PLAY_PATTERN drums
```

Repeats the indented body N times. Loops can contain `PLAY_SEQUENCE`, `PLAY_PATTERN`, and nested `LOOP` blocks.

```
LOOP 2:
    LOOP 4:
        PLAY_SEQUENCE intro
    PLAY_SEQUENCE chorus
```

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

### Looping Melody

```
BPM 140

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 5 30 150 80
    VOLUME 180

SEQUENCE rise:
    PLAY lead C4 0.5
    PLAY lead D4 0.5
    PLAY lead E4 0.5
    PLAY lead F4 0.5
    PLAY lead G4 1
    REST 0.5

SEQUENCE resolve:
    PLAY lead G4 0.5
    PLAY lead F4 0.5
    PLAY lead E4 0.5
    PLAY lead D4 0.5
    PLAY lead C4 2

LOOP 3:
    PLAY_SEQUENCE rise

PLAY_SEQUENCE resolve
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

### Multi-Instrument Track

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
    BEAT 3: kick

LOOP 2:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
    PLAY_PATTERN beat
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

The compiler checks for common mistakes:

| Check | Level | Description |
|-------|-------|-------------|
| Undefined instrument | Error | `PLAY`/`BEAT` references instrument not defined |
| Undefined sequence | Error | `PLAY_SEQUENCE` references sequence not defined |
| Undefined pattern | Error | `PLAY_PATTERN` references pattern not defined |
| Invalid note name | Error | Note doesn't match `[A-G][#sb]?[0-9]` pattern |
| Negative duration | Error | Beat duration <= 0 |
| Volume out of range | Error | Volume not 0-255 |
| Negative ADSR | Error | Any ADSR parameter < 0 |
| LOOP count <= 0 | Error | Loop must repeat at least once |
| Very short ADSR | Warning | ADSR < 5ms (control rate is ~16ms/step) |
| Note outside piano range | Warning | MIDI < 21 or > 108 |
| Too many synths | Warning | > 4 synths (ATmega328 has 2KB RAM) |
| Fast BPM | Warning | BPM > 300 may exceed AVR timing |
| Non-standard audio rate | Warning | Not 16384 or 32768 |
| Beat outside bar | Warning | Beat position > bar length |

---

## Grammar Summary

```
program       := (config | instrument | sequence | pattern | arrangement)* EOF
config        := ("BPM" | "AUDIO_RATE" | "CONTROL_RATE") NUMBER
instrument    := "INSTRUMENT" name ":"
                     ("TYPE" ("SYNTH"|"DRUM")
                    | "WAVE" ("SIN"|"SAW"|"SQUARE"|"TRIANGLE"|"NOISE")
                    | "ADSR" NUMBER NUMBER NUMBER NUMBER
                    | "VOLUME" NUMBER
                    | "FREQ" NUMBER
                    | "DECAY" NUMBER)+
sequence      := "SEQUENCE" name ":"
                     ("PLAY" name NOTE NUMBER | "REST" NUMBER)+
pattern       := "PATTERN" name ":"
                     ("BEAT" NUMBER ":" name)+
arrangement   := (loop | play_seq | play_pat)+
loop          := "LOOP" NUMBER ":" arrangement
play_seq      := "PLAY_SEQUENCE" name
play_pat      := "PLAY_PATTERN" name
```

**Keywords** (must be UPPERCASE): `BPM`, `AUDIO_RATE`, `CONTROL_RATE`, `INSTRUMENT`, `TYPE`, `SYNTH`, `DRUM`, `WAVE`, `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `ADSR`, `VOLUME`, `FREQ`, `DECAY`, `SEQUENCE`, `PATTERN`, `PLAY`, `REST`, `BEAT`, `LOOP`, `PLAY_SEQUENCE`, `PLAY_PATTERN`

**Identifiers** (names): lowercase, can contain letters, digits, underscores. Used for instrument/sequence/pattern names.

**Notes**: `C4`, `D#3`, `Bb2`, `Fs5` — case-insensitive letter, optional accidental, octave number.

**Numbers**: integers or floats (`120`, `0.5`, `16384`).
