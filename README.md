# Cuno

A browser card game for 2–10 friends, playing from their own homes. One person creates a room and shares the 4-letter code or invite link. Everyone joins with a nickname: no accounts, nothing to install.

It follows the standard rules of the classic colour-matching card game. The full rules are in [`cuno_rules.md`](cuno_rules.md).

## Features

- Rooms with a 4-letter code and an invite link (`/r/ABCD`)
- A server-authoritative engine: you never see other players' cards
- Wild Draw Four challenges, the UNO call and Catch, scoring to 500
- Refresh or lose Wi-Fi and you rejoin with your hand intact. Absent players are auto-played by a turn timer
- Animated card flights, a turn countdown ring, a direction indicator, light and dark themes, phone layouts

## Run locally

Requires Python 3.14 with [uv](https://docs.astral.sh/uv/), and Node 20+.

```bash
uv sync
cd web && npm install && npm run build && cd ..
uv run cuno            # http://localhost:8000
```

For frontend development, with hot reload:

```bash
uv run cuno                 # terminal 1: API + WebSocket on :8000
cd web && npm run dev       # terminal 2: http://localhost:5173 (proxies to :8000)
```

To play with friends before deploying, expose your local server with a tunnel, for example `cloudflared tunnel --url http://localhost:8000`, and share the URL.

## Tests

```bash
uv run pytest               # engine rules + rooms/WebSocket
cd web && npm run check     # Svelte/TypeScript type check
```

## Deploy

The `Dockerfile` builds the frontend and runs a single server process on `$PORT`, so any container host works (Fly.io, Render, Railway…). Rooms live in memory, so run **one instance**: a restart ends running games.

```bash
docker build -t cuno .
docker run -p 8000:8000 cuno
```
