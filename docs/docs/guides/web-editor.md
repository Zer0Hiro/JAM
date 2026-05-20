---
sidebar_position: 6
---

# Web Editor

Use the browser-based editor to write, preview, and upload JAM programs.

## Setup

Clone with submodules and run two terminals:

```bash
git clone --recursive https://github.com/Zer0Hiro/JAM-web-edition jamWeb
cd jamWeb
```

If already cloned without `--recursive`:

```bash
git submodule update --init --recursive
```

```bash
# Frontend
npm install
npm run dev          # http://localhost:5173
```

Play and Compile work entirely in the browser via [Pyodide](https://pyodide.org/) (Python-in-WASM). No backend needed for core features.

```bash
# Backend (optional — only for ESP32 upload and JAMai chat)
pip install flask flask-cors
python3 server/app.py  # http://localhost:5050
```

Vite proxies `/api/*` to the Flask backend automatically.

:::info
The frontend alone handles compilation and preview. The backend is only required for ESP32 hardware upload and the JAMai chat assistant.
:::

## Features

### Live Preview

Write JAM code in the editor and click **Play** to compile and hear it instantly as WAV audio — no hardware or server needed. The JAM compiler runs directly in your browser via Pyodide (Python compiled to WebAssembly).

### Compile to C++

Click **Compile** to generate Mozzi C++ source. The output appears in the editor and can be copied for manual upload.

### Upload to ESP32

Click **Upload** to compile and flash directly to a connected ESP32. You can specify the GPIO pin for audio output.

:::warning
USB upload requires the ESP32 to be physically connected and accessible. In WSL2, you need `usbipd-win` for USB passthrough — see the [hardware upload guide](/guides/upload-to-hardware#wsl2-usb-passthrough).
:::

### JAMai Assistant

A floating chat widget that answers questions about JAM syntax and lessons. Powered by local keyword-based RAG — no external AI API required.

:::tip
JAMai runs entirely locally — no API keys or external services needed. It uses keyword-based RAG over the lesson content to answer questions about JAM syntax.
:::

## API Endpoints (server, optional)

| Endpoint | Method | What it does |
|----------|--------|-------------|
| `/api/upload` | POST | Compile + PlatformIO upload. Accepts `pin` for GPIO |
| `/api/jamai/chat` | POST | RAG chat assistant |
| `/api/compile` | POST | Source to C++ + WAV (fallback if Pyodide unavailable) |
| `/api/preview` | POST | Source to WAV only (fallback if Pyodide unavailable) |
| `/api/health` | GET | Status check |

:::note
Compile and preview run client-side by default. The server endpoints are fallback-only. For very large compositions, the CLI compiler may be faster.
:::

## Lessons

The web editor includes 23 interactive lessons that teach JAM from scratch. Available in English and Hebrew. Progress is saved in localStorage.
