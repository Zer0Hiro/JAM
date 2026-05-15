---
sidebar_position: 2
---

# Instruments

Define named instruments with `INSTRUMENT name:` followed by indented properties. Two types: **SYNTH** (melodic) and **DRUM** (percussive).

## Synth Instrument

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 10 50 200 100
    VOLUME 180
```

## Drum Instrument

```
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255
```

## Properties

| Property | Required | Values | Description |
|----------|----------|--------|-------------|
| `TYPE` | yes | `SYNTH`, `DRUM` | Melodic synth or drum hit |
| `WAVE` | yes | `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `PLUCK`, `HANDPAN`, `BELL` | Oscillator waveform |
| `ADSR` | no | `attack decay sustain release` (all in ms) | Envelope shape (SYNTH only) |
| `VOLUME` | no | `0`–`255` (default: `200`) | Channel volume |
| `FREQ` | no | integer Hz | Fixed frequency (DRUM only) |
| `DECAY` | no | integer ms | Decay time (DRUM only) |
| `CUTOFF` | no | `20`–`20000` Hz | Low-pass filter cutoff frequency |
| `RESONANCE` | no | `0`–`255` (default: `0`) | Filter resonance / Q factor |
| `REVERB` | no | `0`–`255` (default: `0`) `[DECAY ms] [ROOM 0.0–1.0]` | Reverb wet/dry mix, with optional decay time and room size |
| `DELAY` | no | `time_ms feedback` (0–2000, 0–255) | Echo delay time and feedback |
| `GLIDE` | no | `0`–`1000` ms (default: `0`) | Portamento / pitch slide time |
| `PAN` | no | `0`–`255` (default: `127`) | Stereo pan (0=left, 127=center, 255=right) |
| `LFO` | no | `rate depth VOLUME\|PITCH\|CUTOFF\|PAN` | Low Frequency Oscillator |
| `VOICES` | no | `1`–`4` (default: `1`) | Number of detuned oscillator voices (unison) |
| `DETUNE` | no | `0`–`100` cents (default: `0`) | Detune spread between voices |
| `CHORUS` | no | `0`–`255` (default: `0`) | Chorus effect wet/dry mix |
| `LEGATO` | no | flag (no value) | Consecutive notes overlap instead of cutting previous note. SYNTH only |
| `POLYPHONY` | no | `1`–`8` (default: `1`) | Max simultaneous notes per instrument |

## Waveforms

| Name | Description |
|------|-------------|
| `SIN` | Sine wave — pure, clean tone |
| `SAW` | Sawtooth — bright, buzzy, good for bass and lead |
| `SQUARE` | Square wave — hollow, retro |
| `TRIANGLE` | Triangle — softer than square, mellow |
| `NOISE` | White noise — percussion, hi-hats, snares |
| `PLUCK` | Karplus-Strong string — guitar, harp, pizzicato |
| `HANDPAN` | Struck metal membrane — additive synthesis (fundamental + octave + octave-fifth + noise transient). SYNTH only. Attack always 1ms, sustain always 0. Default envelope: ADSR 1 600 0 200. Use DECAY to control ring time. |
| `BELL` | Bell — sine with fast-decaying upper harmonics, clean attack transient. SYNTH only. Suggested envelope: ADSR 1 400 0 600. |

:::tip
Start with `SIN` for clean tones, `SAW` for bass, and `NOISE` for percussion. `PLUCK` gives instant guitar-like sounds without complex ADSR tuning.
:::

## ADSR Envelope

```
ADSR attack_ms decay_ms sustain_ms release_ms
```

- **Attack** — time to rise from silence to peak
- **Decay** — time to fall from peak to sustain level
- **Sustain** — time held at sustain level
- **Release** — time to fade to silence after note ends

| Preset | ADSR | Character |
|--------|------|-----------|
| Fast pluck | `ADSR 2 80 0 60` | Instant attack, quick decay, no sustain |
| Slow pad | `ADSR 300 100 400 500` | Gradual swell, long release |
| General purpose | `ADSR 10 50 200 100` | Balanced all-rounder |

## LFO

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

### LFO Syntax

```
LFO <rate> <depth> <target>
```

| Parameter | Range | Description |
|-----------|-------|-------------|
| `rate` | 0.1–20.0 Hz | Oscillation speed (>10 Hz approaches audio range) |
| `depth` | 0–255 | Modulation intensity |
| `target` | `VOLUME`, `PITCH`, `CUTOFF`, or `PAN` | What the LFO modulates |

- **VOLUME LFO** — tremolo effect. Depth controls amplitude swing (255 = full 0-to-max)
- **PITCH LFO** — vibrato effect. Depth is in cents (100 cents = 1 semitone)
- **CUTOFF LFO** — sweeps the low-pass filter ("wah-wah" / acid bass). Depth is in Hz. Instrument must have `CUTOFF` set
- **PAN LFO** — auto-pans across stereo field. Depth is swing range (0–255). Instrument must have `PAN` set. **ESP32 with I2S DAC only** — won't compile on AVR

:::danger
`LFO PAN` requires ESP32 with I2S DAC. Using it on AVR targets will cause a compilation error, not just a warning.
:::

## Unison / Detune / Chorus

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
- `DETUNE > 0` requires `VOICES > 1` (otherwise error)
- `DETUNE > 50` warns about potentially out-of-tune results
- `VOICES` and `DETUNE` have no effect on DRUM instruments

## Extended REVERB Syntax

The `REVERB` property supports optional `DECAY` and `ROOM` parameters:

```
INSTRUMENT pad:
    TYPE SYNTH
    WAVE SIN
    REVERB 180 DECAY 3000 ROOM 0.7
    ADSR 50 100 300 200
    VOLUME 180
```

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| `mix` | 0–255 | 0 | Reverb wet/dry mix (required) |
| `DECAY` | 100–10000 ms | — | Reverb tail length |
| `ROOM` | 0.0–1.0 | — | Room size (0 = small, 1 = cathedral) |

All three apply per-instrument independently. Per-note `REVERB:value` overrides still control mix only.

## LEGATO

Boolean flag — its presence enables legato mode. Consecutive notes overlap rather than cutting the previous note.

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    LEGATO
    ADSR 10 50 200 100
    VOLUME 180
```

- Only valid on `SYNTH` instruments — warning if used on `DRUM`
- Interacts with `POLYPHONY`: if both set, `POLYPHONY` controls max simultaneous voices

:::tip
Combine `LEGATO` with `GLIDE` for smooth, connected melodic lines where notes slide into each other.
:::

## POLYPHONY

Controls how many notes from a single instrument can sound at the same time.

```
INSTRUMENT pad:
    TYPE SYNTH
    WAVE SAW
    POLYPHONY 4
    LEGATO
    ADSR 50 100 300 200
    VOLUME 180
```

| Property | Range | Default | Description |
|----------|-------|---------|-------------|
| `POLYPHONY` | 1–8 | 1 | Max simultaneous notes per instrument |

- Default `1` = monophonic (each new note cuts the previous)
- Warning if total polyphony across all instruments exceeds 8 (AVR RAM)

:::danger
High polyphony values consume significant RAM. On AVR targets (Arduino Uno), keep total polyphony across all instruments at 8 or below.
:::
