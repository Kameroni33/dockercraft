# dockercraft

Self-hosted Minecraft (Java) server manager. A Python FastAPI "manager" orchestrates
per-instance Docker containers, each running one Minecraft server. Vue web UI on top.

**Personal project.** Fresh rebuild — all code on `main`/`python-ui` branches is legacy;
ignore it entirely.

## Architecture

```
┌─────────────────────────────┐
│  Manager (FastAPI)          │  REST + WebSocket API, Vue 3 SPA
│  - docker SDK (socket)      │
│  - SQLite (state/metadata)  │
│  - APScheduler (backups,    │
│    mod auto-updates)        │
└──────────┬──────────────────┘
           │ creates/controls
┌──────────▼──────────────────┐
│  MC instance containers     │  custom slim image: JRE + entrypoint
│  one per server, own ports  │  named volumes: world, mods, config
└─────────────────────────────┘
```

- **Custom MC image** (not itzg): slim JRE base + entrypoint script. The *manager* downloads
  server jars, installs Fabric, manages mods — containers stay dumb.
- **Console access**: container stdin/stdout attach for full interactive console; RCON for
  programmatic commands (backups, save-off, etc.).
- **Version installs**: Mojang piston-meta API (vanilla jars), Fabric Meta API (loader).
  Architecture should leave room for Forge/NeoForge/Paper later.
- **Mods**: Modrinth API — search, install, dependency resolution, MC/loader compatibility
  checks, per-mod auto-update toggle.
- **Backups**: RCON `save-off`/`save-all` → archive world dir → `save-on`. Scheduled via
  APScheduler. Retention policies (count/age). Restore in place or clone into a new instance.
- **State**: SQLite — instances, port allocations, installed mods, backup metadata, settings,
  and a **local player cache** (username ↔ UUID via Mojang API) so known players can be
  conveniently re-whitelisted on new servers.
- **Networking**: each instance gets a distinct host port; manager surfaces LAN address +
  port per instance for router port-forwarding setup.

## Stack

| Layer    | Choice                                          |
|----------|-------------------------------------------------|
| Backend  | Python 3.12+, FastAPI, uvicorn, docker SDK, SQLite (SQLModel), APScheduler |
| Frontend | Vue 3 + Vite + TypeScript                       |
| Infra    | Docker + compose; manager container mounts docker socket |
| Target   | Linux first (Dell workstation, modest specs); AWS-friendly later |

## Repo layout (planned)

```
api/              FastAPI app (routers/, services/, models/, db/)
api/tests/
images/minecraft/ custom MC server image (Dockerfile, entrypoint)
web/              Vue 3 app
compose.yml       runs the manager
install.sh        first-time host setup (docker, dirs, compose up)
```

## Feature plan & status

### Phase 1 — Core orchestration (MVP)
- [x] Project scaffolding: `api/` package, compose, custom MC image
- [x] Instance lifecycle: create / start / stop / restart / delete via docker SDK
- [x] Port allocation (lowest-free in configured ranges, done at instance create)
- [x] Vanilla version installer (piston-meta, any version, dynamic download)
- [x] Fabric loader installer (Fabric Meta API)
- [x] server.properties / whitelist / ops management per instance
- [x] Local player cache (username/UUID) in DB for quick whitelisting across servers
- [x] Address visibility endpoint (LAN IP + ports per instance)
- [x] Interactive console (WebSocket attach to container stdio) + RCON
- [x] Interactive new-server setup flow (API-level: version, loader, settings)

### Phase 2 — Mods & backups
- [x] Backup engine: scheduled snapshots, retention policies
- [x] Restore in place / spin up new instance from backup
- [x] Modrinth integration: search, install, compatibility check, dependencies
- [x] Per-mod auto-update toggle + scheduled update checks
- [x] Per-instance extra port mappings (e.g. Geyser Bedrock UDP 19132)

### Phase 3 — Web UI (Vue 3)
- [ ] Dashboard: instance list, status, addresses, start/stop
- [ ] Instance detail: settings editor, live console, player/whitelist mgmt
- [ ] Mod browser (Modrinth search/install) + backup management
- [ ] New-server setup wizard

### Phase 4 — Ops & beyond
- [ ] `install.sh` one-shot setup on fresh Linux host
- [ ] Resource limits per instance (RAM/CPU caps — workstation has modest specs)
- [ ] Auth for the manager (needed before any non-LAN exposure)
- [ ] Bind RCON host ports to 127.0.0.1 only (currently 0.0.0.0; password-protected,
      fine on LAN, must fix before internet-facing hosting)
- [ ] AWS/cloud deployment story
- [ ] Other loaders: Forge / NeoForge / Paper

### First real-world goal
Vanilla-feel Fabric server for Kameron's brother + friends, **cross-platform**
(Bedrock support via Geyser + Floodgate Fabric mods). Phases 1–2 must support this.

## Conventions

- Python: type hints everywhere, `ruff` for lint/format, `pytest` for tests
- Async-first FastAPI; docker SDK calls wrapped in a service layer (`services/docker_manager.py`)
- All external APIs (Mojang, Fabric, Modrinth) behind thin client modules — easy to mock/test
- Design for maximum customization: prefer config/data-driven behavior over hardcoding
- Keep this file current: update status checkboxes and decisions as work lands

## Workflow

- **Check in between stages**: pause after each phase/stage for an architecture-direction
  review before continuing
- **Commit in small, stable chunks** — each commit should leave the project working

## Status log

- 2026-06-06: Project restarted from scratch. Architecture + stack decided. No code yet.
- 2026-06-06: Scaffolding done — `api/` package (FastAPI + SQLModel + health endpoint),
  venv tooling (ruff/pytest green), manager Dockerfile + compose, custom MC image
  (`dockercraft/minecraft:javaNN`, per-Java-major builds, uid-1000 `minecraft` user,
  fail-loud entrypoint; provisioning is the manager's job).
- 2026-06-06: Instance lifecycle done — ServerInstance model (DB = declared config,
  Docker = live status), docker_manager service layer, port allocator, /servers CRUD +
  start/stop/restart. 10 tests green, live smoke-tested against real docker socket.
- 2026-06-06: Installers done — mojang + fabric clients (sha1-verified downloads, jar
  cache under data/cache/), provision service (sets java_major from piston-meta,
  explicit EULA gate), /versions discovery endpoints. NOTE: MC now uses year-based
  versions (26.1.x); fabric launcher jar self-fetches the vanilla jar on first boot.
- 2026-06-06: Config + players done — server.properties PATCH (managed keys enforced,
  re-asserted pre-start), whitelist/ops endpoints, Player cache (username↔UUID,
  case-insensitive, Mojang fallback; 400 AND 404 from Mojang = unknown player).
- 2026-06-06: **Phase 1 COMPLETE.** Console (from-scratch RCON client + WS attach
  bridge), /addresses, POST /servers/setup wizard (EULA gate, rollback on failure).
  Verified e2e: real Fabric server on MC 26.1.2 (needed Java 25 — image auto-built),
  RCON commands, live whitelist, WS console stdin/stdout, graceful stop/delete.
  38 unit tests green. Next: Phase 2 (Modrinth mods, backups) after stage review.
- 2026-06-06: **Phase 2 COMPLETE.** Backups (hot via RCON save-off/flush/save-on,
  retention policies, APScheduler sweep, restore-in-place w/ pre_restore safety,
  clone-to-new-instance, backups outlive instance deletion). Modrinth (search,
  install w/ recursive required-dep resolution, sha512 verify, .disabled toggle,
  auto-update sweep). Extra port mappings per instance. Verified live: Geyser +
  Floodgate + auto-resolved Fabric API on MC 26.1.2, Bedrock UDP 19132 bound on
  host, whitelist intact, 148 MB hot backup of the running modded server.
  59 unit tests green. Notes: Floodgate is optional-dep on Modrinth — install
  explicitly; backup includes fabric libs (~148 MB) — could exclude rebuildable
  caches later. Next: Phase 3 (Vue UI) after stage review.
