# HarborPilot Desktop (WIP)

This folder hosts the desktop shell (Electron + React/Vite/TS/Tailwind) and a local Python backend.
The UI is placeholder-only and will be replaced by the Figma build.

## Backend (Python)

Install deps:
```
python -m pip install -r desktop/backend/requirements.txt
```

Run:
```
python desktop/backend/server.py --port 5179 --token dev --workspace <path-to-workspace>
```

## Desktop shell (Electron + React)

Install deps:
```
cd desktop
npm install
```

Run (dev):
```
npm run dev
```

This starts Vite at `http://localhost:5173` and Electron will auto-connect.

## Environment variables

- `HARBORPILOT_PYTHON`: Python executable for Electron to spawn (default: `python`)
- `HARBORPILOT_WORKSPACE`: workspace root (must include `docs/`)
- `HARBORPILOT_DEV_SERVER_URL`: override renderer URL (dev)
- `HARBORPILOT_TOKEN`: backend auth token (optional)
- `HARBORPILOT_CORS_ORIGINS`: comma-separated CORS allowlist
