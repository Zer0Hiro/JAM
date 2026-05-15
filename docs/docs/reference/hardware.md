---
sidebar_position: 4
---

# Hardware Targets

## Supported Boards

| Board | Platform | Audio Output | Stereo |
|-------|----------|-------------|--------|
| ESP32 (esp32dev) | pioarduino | Internal DAC (GPIO 25) or I2S DAC | Yes (I2S DAC) |
| Arduino Uno | ATmega328P | PWM output on pin 9 | No (mono only) |

Configuration is in `platformio.ini`. ESP32 is the primary target.

## Stereo Features

`PAN` and `LFO PAN` require ESP32 with an I2S DAC. When any instrument uses `LFO PAN`, the compiler emits `MOZZI_STEREO` and `MOZZI_OUTPUT_I2S_DAC` config macros and guards with `#ifdef __AVR__ #error`.

## ESP32 Upload (WSL2)

Requires `usbipd-win` for USB passthrough and user in `dialout` group. PlatformIO must be on PATH (`pip install platformio`).
