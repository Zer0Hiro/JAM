---
sidebar_position: 3
---

# Drum Patterns

Create beats using the beat-grid pattern system.

## Define Drum Instruments

Drums use `TYPE DRUM` with a fixed frequency and decay time instead of ADSR:

```
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
```

Common drum recipes:
- **Kick** — SIN wave, low FREQ (40–80 Hz), medium DECAY
- **Snare** — NOISE wave, mid FREQ (150–300 Hz), short DECAY
- **Hi-hat** — NOISE wave, high FREQ (600–1200 Hz), very short DECAY

:::tip
Experiment with `FREQ` values to shape your drum sound. Lower frequencies make deeper kicks, higher frequencies make brighter snares.
:::

## Write a Pattern

Patterns place instruments on beat positions in a bar (default: 4 beats):

```
PATTERN basic_beat:
    BEAT 1: kick
    BEAT 1: hat
    BEAT 2: snare
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat
```

Beat positions are 1-based. Same beat number = simultaneous (kick + hat on beat 1). Fractional positions create offbeats:

:::note
Beat positions beyond 4 will trigger a compiler warning, since the default bar length is 4 beats (4/4 time).
:::

```
PATTERN groove:
    BEAT 1: kick
    BEAT 1: hat
    BEAT 1.5: hat        # offbeat hi-hat
    BEAT 2: snare
    BEAT 2: hat
    BEAT 2.5: hat
    BEAT 3: kick
    BEAT 3.5: kick       # ghost kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat
    BEAT 4.5: hat
```

## Play the Pattern

```
LOOP 8:
    PLAY_PATTERN basic_beat
```

Each `PLAY_PATTERN` plays one bar. Loop it to repeat.

## Combine with Melody

Use `PLAY_TOGETHER` to layer drums with other sequences:

```
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN basic_beat
```

## Velocity for Dynamics

Add velocity (0–255) to create accents:

:::info
Velocity is optional. When omitted, the instrument plays at its full `VOLUME`. Use velocity to add musical dynamics without changing the instrument definition.
:::

```
PATTERN dynamic_beat:
    BEAT 1: kick 255           # loud downbeat
    BEAT 1: hat 180
    BEAT 1.5: hat 100          # quiet ghost hat
    BEAT 2: snare 220
    BEAT 2: hat 140
    BEAT 3: kick 200
    BEAT 3: hat 180
    BEAT 4: snare 255          # accent on 4
    BEAT 4: hat 140
```

## Full Example

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
