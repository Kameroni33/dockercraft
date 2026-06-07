# dockercraft

Self-hosted Minecraft (Java) server manager with a web UI. One FastAPI manager
orchestrates any number of Minecraft servers as Docker containers: version
installs (vanilla + Fabric), Modrinth mods with dependency resolution and
auto-updates, hot backups with retention policies, live console, whitelist
management with a cross-server player cache, and one-click Bedrock
cross-platform support (Geyser + Floodgate).

## Install (Linux)

```shell
git clone <repo> dockercraft && cd dockercraft
./install.sh
```

The installer checks Docker, writes `.env` (data dir, LAN IP, a free port),
builds, and starts the manager. Open the printed URL — the first visit creates
the admin account.

Everything lives under `./data/` (worlds, backups, the manager DB). Re-run
`./install.sh` after a `git pull` to update.

## Development

```shell
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn api.main:app --reload          # API on :8000
cd web && npm install && npm run dev              # UI on :5173, proxies /api
.venv/bin/pytest && .venv/bin/ruff check api/     # tests + lint
```

Architecture, full feature plan, and project status: see [CLAUDE.md](CLAUDE.md).
