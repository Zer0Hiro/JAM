---
sidebar_position: 4
---

# Examples

## Hello World — Single Tone

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

## Full Band with PLAY_TOGETHER

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

## Drum Pattern

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

## Chord Progression

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

## Effects and Panning

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

## Envelope Shaping (Pad + Pluck)

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

## Bell Melody in 3/4

Demonstrates TIME_SIGNATURE, WAVE BELL, LEGATO, POLYPHONY, extended REVERB, and smooth BPM ramp.

```
BPM 92
TIME_SIGNATURE 3 4

INSTRUMENT bell:
    TYPE SYNTH
    WAVE BELL
    ADSR 1 400 0 600
    REVERB 160 DECAY 4000 ROOM 0.8
    LEGATO
    POLYPHONY 3
    VOLUME 190

INSTRUMENT chime:
    TYPE SYNTH
    WAVE BELL
    ADSR 1 300 0 400
    REVERB 120 DECAY 2000 ROOM 0.5
    POLYPHONY 2
    PAN 80
    VOLUME 150

INSTRUMENT low_bell:
    TYPE SYNTH
    WAVE BELL
    ADSR 1 500 0 800
    REVERB 200 DECAY 5000 ROOM 0.9
    LEGATO
    POLYPHONY 2
    PAN 180
    VOLUME 170

SEQUENCE waltz_melody:
    VELOCITY_CURVE CRESCENDO 100 200 6
    PLAY bell E5 1
    PLAY bell D5 0.5
    PLAY bell C5 0.5
    PLAY bell B4 1
    PLAY bell A4 1.5
    PLAY bell G4 1.5

SEQUENCE waltz_chords:
    PLAY chime [C4 E4 G4] 3
    PLAY chime [A3 C4 E4] 3
    PLAY chime [F3 A3 C4] 3
    PLAY chime [G3 B3 D4] 3

SEQUENCE bass_bells:
    PLAY low_bell C3 2
    REST 1
    PLAY low_bell A2 2
    REST 1
    PLAY low_bell F2 2
    REST 1
    PLAY low_bell G2 2
    REST 1

PATTERN waltz_tap:
    BEAT 1: bell E6 0.5 180
    BEAT 2: bell E6 0.5 100
    BEAT 3: bell E6 0.5 100

FADE_IN 3
LOOP 2:
    PLAY_TOGETHER:
        PLAY_SEQUENCE waltz_melody
        PLAY_SEQUENCE waltz_chords
        PLAY_SEQUENCE bass_bells
        PLAY_PATTERN waltz_tap

BPM 80 OVER 6
VELOCITY_CURVE DECRESCENDO 200 60 6

LOOP 1:
    PLAY_TOGETHER:
        PLAY_SEQUENCE waltz_melody
        PLAY_SEQUENCE waltz_chords
        PLAY_SEQUENCE bass_bells

FADE_OUT 6
LOOP 1:
    PLAY_TOGETHER:
        PLAY_SEQUENCE waltz_chords
        PLAY_SEQUENCE bass_bells
```
