---
sidebar_position: 2
---

# Your First Song

Build a complete multi-instrument song from scratch.

## Step 1: Set the Tempo

Every song starts with a tempo. 120 BPM is a good default — moderate pace, easy to count.

```
BPM 120
```

## Step 2: Define Instruments

Create a bass synth and a lead melody:

```
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
```

**WAVE** picks the oscillator character — SAW is bright and buzzy (good for bass), TRIANGLE is softer (good for melodies).

**ADSR** shapes each note's volume over time: Attack (rise), Decay (fall from peak), Sustain (hold), Release (fade after note ends). All values in milliseconds.

:::tip
Not sure what envelope to use? Start with `ADSR 10 50 200 100` — it works for most instruments. Tweak from there.
:::

## Step 3: Write Sequences

A sequence is a list of notes that play one after another:

```
SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass C2 1
    PLAY bass G2 1
    PLAY bass F2 1

SEQUENCE melody:
    PLAY lead E4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1
    REST 0.5
    PLAY lead G4 0.5
    PLAY lead E4 1
```

Each `PLAY` takes: instrument name, note, and duration in beats. `REST` adds silence.

## Step 4: Arrange the Song

Play both sequences together and loop them:

```
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
```

`PLAY_TOGETHER` merges them onto one timeline — without it, bass would play first, then melody.

:::warning
Without `PLAY_TOGETHER`, sequences play one after another — bass finishes completely before melody starts. This is the most common beginner mistake.
:::

## Full Program

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

SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass C2 1
    PLAY bass G2 1
    PLAY bass F2 1

SEQUENCE melody:
    PLAY lead E4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1
    REST 0.5
    PLAY lead G4 0.5
    PLAY lead E4 1

LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
```

## Try It

```bash
python3 -m dsl.compiler song.jam --wav -o song.wav
```

## Next Steps

:::info
Every example in this guide is a complete, valid `.jam` file. Copy any code block and compile it directly.
:::

- Add drums — see [Drum Patterns](./drum-patterns)
- Add effects — see [Effects and Mixing](./effects-and-mixing)
- Try chords: `PLAY lead [C4 E4 G4] 2`
