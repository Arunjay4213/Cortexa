# CortexOS

An observability layer for AI agent memory.

CortexOS sits between a memory system and the LLM that reads from it.
For each retrieval it records which memories were returned, scores how much each one influenced the response, tracks what the retrieved context cost in tokens, and keeps a provenance graph so a stored memory can be traced back to the interaction that created it.
It is meant to sit on top of the memory system you already have, and the SDK ships as a wrapper around any Mem0-compatible client.

Live site: [cortexadev.com](https://cortexadev.com)

## Repository layout

This is a monorepo with three independent subprojects.

| Directory | Stack | What it is |
|---|---|---|
| `cortex-engine` | Python 3.11+, FastAPI, SQLAlchemy, Postgres | The backend API and attribution engine |
| `cortex-dashboard` | Next.js 16, React 19, TypeScript, Tailwind CSS 4 | The operator dashboard UI |
| `cortex-os` | Vite 6, React 18, TypeScript, Tailwind CSS 4 | The public marketing and docs site |

### cortex-engine

The backend is a FastAPI application (`cortex.api.app:app`) that exposes a REST API under `/api/v1` with five routers:

- `memories`: create, list, fetch and delete memory units.
- `transactions`: a two-phase retrieval protocol; a search initiates a pending transaction, and reporting the model's response completes it and triggers scoring.
- `attribution`: attribution scores per transaction and per memory.
- `health`: per-agent health and contradiction checks.
- `dashboard`: an aggregated overview endpoint.

A plain `/healthz` endpoint is served at the root for liveness checks.

Attribution uses EAS (Embedding Attribution Score), implemented in `cortex/attribution/eas.py`.
It scores each retrieved memory by the product of its cosine similarity to the response and its cosine similarity to the query, then normalizes the scores so they sum to 1.
The computation is a numpy batch matrix multiply over the retrieved set, so it is O(k*d) in the number of retrieved memories and the embedding dimension.
Embeddings come from `sentence-transformers` using `all-MiniLM-L6-v2` at 384 dimensions by default.

Persistence is Postgres via async SQLAlchemy and `asyncpg`, with three Alembic migrations covering the initial schema, calibration and cost configuration, and the provenance graph.
The provenance design is written up in `cortex-engine/PROVENANCE.md` and `cortex-engine/docs/provenance-graph.md`.

`cortex/sdk/wrapper.py` provides `CortexMemory`, an OpenTelemetry-instrumented wrapper around a Mem0-compatible client.
Every backend call in the wrapper is guarded, so the SDK does not crash the host application if the engine is unreachable.

Tests live in `cortex-engine/tests` and run under pytest with `asyncio_mode = "auto"`.

### cortex-dashboard

The dashboard is built on the Next.js App Router and has pages for the overview, agents, memory, memory flow, attribution, cockpit, terminal, health, compliance, analytics, alerts, engine status, settings and docs.
Charts and graph views are built with Recharts, D3, React Flow and Framer Motion.

`cortex-dashboard/lib/engines` holds TypeScript implementations of two attribution algorithms, ContextCite and Shapley value computation, plus a metrics calculator, with Jest tests for all three.
Several dashboard views are driven by `lib/mock-data.ts` instead of live engine data.
The `/engine` page polls `http://localhost:8000/healthz` to show whether the Python backend is running.
`cortex-dashboard/README.md` is the longer product write-up and demo walkthrough.

### cortex-os

The public site is a Vite and React single-page app with client-side routing for `/`, `/docs` and `/manifesto`, and it has the hero, trace demo, provenance graph, cost section, FAQ and waitlist sections.
`.github/workflows/deploy.yml` builds this project on every push to `main` and publishes `cortex-os/dist` to GitHub Pages, served at the custom domain in `cortex-os/public/CNAME`.

## Running locally

### cortex-engine

Requires Python 3.11 or newer and a running Postgres instance.

```bash
cd cortex-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn cortex.api.app:app --reload --port 8000
```

The API is then on `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

Settings are read from the environment with the `CORTEX_` prefix, so the database connection can be overridden with `CORTEX_DATABASE_URL` and `CORTEX_DATABASE_URL_SYNC`.
The defaults point at `postgresql://postgres:cortex@localhost:5432/cortex`.
CORS defaults allow `http://localhost:3000` and `http://localhost:3001`.

Run the tests with:

```bash
pytest
```

### cortex-dashboard

Requires Node.js 20 or newer.

```bash
cd cortex-dashboard
npm install
npm run dev
```

The dashboard runs on `http://localhost:3000`.
It renders without the backend, but the engine page will report the API as offline until `cortex-engine` is running on port 8000.

The other scripts are `npm run build`, `npm start`, `npm run lint`, `npm test`.

### cortex-os

```bash
cd cortex-os
npm install
npm run dev
```

Vite serves the site on `http://localhost:5173`.
Use `npm run build` to type-check and produce `dist`, and `npm run preview` to serve that build.
