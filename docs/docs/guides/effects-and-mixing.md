---
sidebar_position: 4
---

# Effects and Mixing

Add depth and character to your music with built-in effects.

## Filter (CUTOFF + RESONANCE)

Low-pass filter removes high frequencies. Lower CUTOFF = darker, warmer sound:

```
INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 600         # only frequencies below 600 Hz pass through
    RESONANCE 100      # boost around the cutoff point
    ADSR 5 40 300 120
    VOLUME 220
```

You can override CUTOFF per-note for expressive playing:

```
SEQUENCE bass_filter:
    PLAY bass C2 1 200 CUTOFF:400    # dark
    PLAY bass C2 1 200 CUTOFF:1200   # bright
    PLAY bass C2 1 200 CUTOFF:600    # back to normal
```

## Reverb

Adds space and ambience. Value 0–255 (0 = dry, 255 = fully wet):

```
INSTRUMENT pad:
    TYPE SYNTH
    WAVE SIN
    REVERB 150
    ADSR 200 100 400 300
    VOLUME 160
```

## Delay

Echo effect with configurable time and feedback:

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    DELAY 300 150      # 300ms delay, 150 feedback (0-255)
    ADSR 10 30 200 100
    VOLUME 180
```

Higher feedback = more echo repeats. Keep below 200 to avoid runaway feedback.

:::warning
Delay feedback values above 200 can cause audio to build up and clip. Start low and increase gradually.
:::

## Panning (PAN)

Position instruments in the stereo field:

```
INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    PAN 100            # slightly left
    ...

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    PAN 180            # slightly right
    ...
```

Values: 0 = hard left, 127 = center, 255 = hard right.

:::note
Stereo panning requires ESP32 with an I2S DAC. Arduino Uno is mono only.
:::

## Glide (Portamento)

Slide between notes instead of jumping:

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    GLIDE 100          # 100ms slide between notes
    ADSR 10 30 200 100
    VOLUME 180
```

## LFO (Low Frequency Oscillator)

Add movement with slow modulation:

```
INSTRUMENT wobble:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 2000
    VOLUME 200
    ADSR 5 40 300 120
    LFO 4.0 120 VOLUME     # tremolo — volume wobbles at 4 Hz
    LFO 2.0 30 PITCH       # vibrato — pitch wobbles at 2 Hz
    LFO 1.5 800 CUTOFF     # wah — filter sweeps at 1.5 Hz
```

:::tip
LFO on CUTOFF is the secret weapon for electronic music — it creates the classic "wah-wah" and acid bass sounds. Make sure the instrument has `CUTOFF` set first.
:::

Each instrument supports up to 4 LFOs (one per target: VOLUME, PITCH, CUTOFF, PAN).

## Unison (Fat Sound)

Stack detuned copies of an oscillator:

```
INSTRUMENT supersaw:
    TYPE SYNTH
    WAVE SAW
    VOICES 3           # 3 oscillator copies
    DETUNE 20          # spread 20 cents apart
    CHORUS 80          # add chorus width
    ADSR 10 50 200 100
    VOLUME 180
```

:::warning
`VOICES > 2` uses significant RAM on Arduino Uno (ATmega328 has only 2 KB). Stick to 1–2 voices on AVR targets, or use ESP32.
:::

## Volume Dynamics

### VELOCITY_CURVE

Automatically create crescendo/decrescendo across notes:

```
SEQUENCE buildup:
    VELOCITY_CURVE CRESCENDO 40 230 6
    PLAY lead C4 0.5
    PLAY lead D4 0.5
    PLAY lead E4 0.5
    PLAY lead F4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1
```

### FADE_IN / FADE_OUT

Fade the entire mix:

```
FADE_IN 4
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE melody
        PLAY_PATTERN drums
FADE_OUT 8
LOOP 2:
    PLAY_SEQUENCE outro
```

## Mixing Tips

1. **Bass instruments** — keep PAN centered (127), CUTOFF low (400–800)
2. **Lead instruments** — pan slightly off-center, add REVERB or DELAY for space
3. **Hi-hats** — pan slightly (100 or 160), keep VOLUME lower than kick/snare
4. **Use VELOCITY_CURVE** for buildups before a chorus
5. **LFO on CUTOFF** creates movement in pads and bass lines

:::info
All effect values are compile-time constants — they get baked into the C++ output with zero runtime overhead on the MCU.
:::
