# BlendLab web app

React + Vite + Framer Motion. FastAPI serves the built files from `web/dist` at `/`.

```bash
cd web
npm ci            # install (exact versions from package-lock.json)
npm run dev       # http://localhost:5173, talks to the server on :8000
npm test          # unit and component tests
npm run build     # production build into web/dist
```

## No server needed: demo mode

Open `http://localhost:5173/?mock=1`. All data and answers are fake (from `contracts/mocks`).
In the browser console, `blendlabMock.drop()` simulates a lost connection and `blendlabMock.restore()` brings it back.

## Real server

```bash
# terminal 1, from the repo root
FAKE_GENERATOR=true uvicorn src.server.main:app --port 8000     # or DEV_MODEL_OVERRIDE=<a .gguf file> for real tokens
# terminal 2
cd web && npm run dev
```

## Layout

| Path | What it is |
|---|---|
| `src/api/api.js` | The only file that talks to the server (REST, one shared WebSocket, reconnect, ping/pong) |
| `src/api/mock.js` | The same functions, fake. Switched on with `?mock=1` |
| `src/state/` | Chat state: a pure reducer plus the hook that connects it to the API |
| `src/components/` | Top bar, blend dock with the slider, chat, composer, capability curve, Best Blend Finder |
| `src/styles/` | Design tokens (colours, type, spacing) and the stylesheet |

Colours and type come from the Nap in a Boat deck: deep maroon, blush pink, one gold accent, Anton for headings, DM Sans for text.
