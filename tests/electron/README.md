# Playwright Electron Tests

## Prereqs
- `npm install`
- `npx playwright install`

## Running
```bash
npm run test:electron
```

## Notes
- If `frontend/dist/index.html` exists, tests load it directly.
- Otherwise set `HARBORPILOT_DEV_SERVER_URL` to a running dev server URL.
- `.venv` is preferred for backend start. Override with `HARBORPILOT_PYTHON`.
