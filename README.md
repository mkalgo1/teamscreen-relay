# TeamScreen Relay // Executive Fleet Live Screen Observation System

High-performance, ultra-low CPU/RAM desktop screen observation and real-time guidance suite for executive leaders and remote teams.

## Architecture

- **Live Relay Hub (Vercel)**: Next.js edge-ready server hosting the `/api/ping` live presence endpoint, WebRTC/frame signaling, and the browser-accessible CEO Command Hub.
- **Worker Node (`WorkerRelay.exe`)**: Minimalist Windows workstation client (<1% CPU, ~28MB RAM). Uses direct DX/GDI screen capture via `mss` to stream high-definition display feeds and receive real-time CEO guidance prompts.
- **CEO Command Center (`CEOAdmin.exe`)**: Luxury obsidian desktop dashboard for the CEO to monitor the entire worker fleet, inspect live ping times, view screens in high framerate, and send instant guidance instructions.

## Live Endpoints

- `POST /api/ping`: Workstation presence heartbeat and stream status handshake.
- `GET /api/workers`: Fleet roster with live connection metrics and active statuses.
- `POST /api/stream/session`: Start/stop observation sessions and dispatch CEO guidance messages.
- `POST /api/stream/frame` & `GET /api/stream/frame`: Ultra-low latency frame buffer pipeline.

## Desktop Applications

Pre-compiled standalone Windows executables are located in `desktop-apps/bin/`:
- `WorkerRelay.exe`: Distribute to workers/agents.
- `CEOAdmin.exe`: Run on CEO / Manager workstations.

Source code and build instructions are available in `desktop-apps/src/`.
