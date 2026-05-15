---
sidebar_position: 6
---

# Web Editor

Use the browser-based editor to write, preview, and upload JAM programs.

## Setup

Run two terminals:

```bash
# Terminal 1 — Frontend
cd jamWeb
npm install
npm run dev          # http://localhost:5173

# Terminal 2 — Backend
cd jamWeb
pip install flask flask-cors
python3 server/app.py  # http://localhost:5050
```

Vite proxies `/api/*` to the Flask backend automatically.

:::info
Both the frontend and backend must be running simultaneously. The frontend alone cannot compile or preview JAM code.
:::

## Features

### Live Preview

Write JAM code in the editor and click **Preview** to compile and hear it instantly as WAV audio — no hardware needed.

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

## API Endpoints

| Endpoint | Method | What it does |
|----------|--------|-------------|
| `/api/compile` | POST | Source to C++ + WAV (base64). Max 50KB source |
| `/api/preview` | POST | Source to WAV only |
| `/api/upload` | POST | Compile + PlatformIO upload. Accepts `pin` for GPIO |
| `/api/health` | GET | Status check |
| `/api/jamai/chat` | POST | RAG chat assistant |

:::note
The `/api/compile` endpoint has a 50KB source size limit. For very large compositions, use the CLI compiler directly.
:::

## Lessons

The web editor includes 23 interactive lessons that teach JAM from scratch. Available in English and Hebrew. Progress is saved in localStorage.
