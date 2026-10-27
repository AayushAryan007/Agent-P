# AGENT-P frontend

Vite + React + TypeScript single-page app. Static build, deployed on Vercel with Root Directory `frontend/`.

```bash
cp .env.example .env.local   # VITE_API_URL — public, never put secrets here
npm install
npm run dev                  # http://localhost:5173  (design preview: /dev/preview)
npm run lint && npm run typecheck && npm test && npm run build
```

Structure: `src/api` (REST client, queries, types) · `src/domain` (event schema and the run-state reducer shared by live view and replay) · `src/features/*` (screens) · `src/components` (shell and UI primitives). Design tokens live in `src/index.css`; see `docs/DESIGN_SYSTEM.md`.
