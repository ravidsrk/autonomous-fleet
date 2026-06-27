# autonomous-fleet docs site (Starlight)

Stage 2 of `docs/plans/docs-site-plan-2026-06-24.md`. Source of truth remains
`docs/guide/`; this directory builds a searchable Starlight site from it.

## Local development

```bash
cd docs-site
npm install
npm run dev
```

`npm run build` runs `scripts/sync_guide_starlight.py` first (via `prebuild`).

## Deploy

GitHub Actions workflow `.github/workflows/docs-site.yml` builds on push to
`main`. Point Cloudflare Pages (or any static host) at `docs-site/dist/`.

Custom domain target: `autonomous-fleet.dev` (operator-owned DNS).