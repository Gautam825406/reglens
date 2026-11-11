# RegLens — Frontend

Vite + React + TypeScript. Talks to the backend **only** over REST
(`src/api.ts`), with the base URL from `VITE_API_URL`
(default `http://localhost:8000`). No backend code lives in this folder.

## Run (local)

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build (tsc + vite)
```

Set `VITE_API_URL` to point at a backend elsewhere, e.g.:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

## Screens

Landing page (nav, hero, preview, problem/solution, features, how it works,
industries, security, FAQ, footer) · Auth (sign up / sign in / forgot /
reset password, email-verification stub) · App shell with sidebar:
Overview, Document Library, Upload, AI Ask, Compare, Conflict Detection,
Obligation Register, Knowledge Graph, Answer History, Evidence Packs,
Evaluation & Admin, Settings.

Light + dark mode throughout; responsive desktop / tablet / mobile.
