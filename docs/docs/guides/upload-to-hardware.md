---
sidebar_position: 5
---

# Upload to Hardware

Flash your JAM music to an ESP32 or Arduino.

## Requirements

- [PlatformIO](https://platformio.org/) installed (`pip install platformio`)
- ESP32 development board (primary target) or Arduino Uno
- USB cable

:::info
PlatformIO handles all board-specific toolchains and libraries automatically — you don't need to install the Arduino IDE or Mozzi separately.
:::

## Compile to C++

```bash
python3 -m dsl.compiler your_song.jam -o src/main.cpp
```

This generates a Mozzi 2.0 sketch ready for PlatformIO.

## Upload with PlatformIO

```bash
pio run --target upload
```

The `platformio.ini` in the repo is pre-configured for ESP32 (esp32dev). For Arduino Uno, change the environment in `platformio.ini`.

:::warning
If your game or project is installed in a non-standard location, make sure `platformio.ini` points to the correct board environment before uploading.
:::

## Hardware Targets

| Board | Audio Output | Stereo Support |
|-------|-------------|----------------|
| ESP32 (esp32dev) | Internal DAC (GPIO 25) or I2S DAC | Yes (with I2S DAC) |
| Arduino Uno (ATmega328P) | PWM on pin 9 | No (mono only) |

## ESP32 Audio Output

By default, audio outputs through GPIO 25 (internal DAC). For better quality, connect an I2S DAC module.

When your program uses stereo features (`PAN`, `LFO PAN`), the compiler automatically emits I2S DAC configuration.

:::danger
Using stereo features (`PAN`, `LFO PAN`) on Arduino Uno will cause a compilation error. These features require ESP32 with an I2S DAC.
:::

## Upload via Web Editor

The JAM web editor can upload directly to hardware:

1. Open the web editor (`npm run dev` in jamWeb)
2. Write or paste your JAM code
3. Click "Upload to ESP32"
4. Select your GPIO pin if needed

## WSL2 USB Passthrough

If using Windows Subsystem for Linux:

1. Install [usbipd-win](https://github.com/dorssel/usbipd-win) on Windows
2. Add your user to the `dialout` group:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
3. Attach the USB device from Windows PowerShell:
   ```powershell
   usbipd list
   usbipd bind --busid <BUS-ID>
   usbipd attach --wsl --busid <BUS-ID>
   ```
4. Upload normally with `pio run --target upload`

:::tip
After attaching USB in WSL2, run `ls /dev/ttyUSB*` to verify the device is visible before uploading.
:::

## Troubleshooting

- **Permission denied on /dev/ttyUSB0** — add yourself to `dialout` group and log out/in
- **Board not found** — check `platformio.ini` environment matches your board
- **RAM warnings** — reduce `VOICES` count or number of simultaneous synths (ATmega328 has only 2 KB RAM)
- **Stereo features on Arduino** — `PAN` and `LFO PAN` require ESP32 with I2S DAC; compiler will error on AVR
