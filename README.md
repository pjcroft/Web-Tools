# pjcroft web tools

Source for the forward-facing tools on pjcroft.ddnsfree.com (public, no login).

- `pc-plan/` — PC Plan Gantt (Python/Java backend, Docker). Public at /pc-plan/.
- `pc-slide-studio/` — PC Slide Studio (Flask/Docker PowerPoint creator). Public at /pc-slide-studio/.
- `pc-form-studio/` — PC Form Studio (static, fully client-side). Public at /pc-form-page-studio/.

## Deployment (not in this repo)

Live deployment config — docker-compose services, Caddy reverse-proxy blocks, and the
local hub — lives in the private `pjcroft/dashboards` repo. This repo holds only
the apps' source, so a new version is: update the source here, rsync it to
Blue-Deb, rebuild the container (PC Plan / Slide Studio) or rsync the static
files (Form Studio), and verify public, local-hub, and LAN copies.

## Secrets — never commit these

PC Slide Studio reads its OpenRouter key from a server-side `.env` on Blue-Deb
(`OPENROUTER_API_KEY`). That file is **not** in this repo and must never be
added: it is covered by `.gitignore`, along with `openrouter-key.env`.
`/api/status` only reports whether a key is configured; the key itself is
never exposed to the browser. See `pc-slide-studio/README.md` for the app's
own docs. The `.env.example` file in that folder is a placeholder only.
