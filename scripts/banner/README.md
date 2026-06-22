# Banner Generation

All 28 banners in this repo (1 hero + 3 tier + 24 per-skill) are generated with Nano Banana Pro (Google Gemini 3 Pro Image) via OpenRouter.

# Layout

- `banner-prompt.txt` — main hero banner (`assets/banner.png`)
- `tier-infrastructure-prompt.txt` — Tier 1 banner (`assets/tier-infrastructure.png`)
- `tier-adapters-prompt.txt` — Tier 2 banner (`assets/tier-adapters.png`)
- `tier-missions-prompt.txt` — Tier 3 banner (`assets/tier-missions.jpg`)
- Per-skill prompts live next to the images they produce at `skills/<name>/assets/banner-prompt.txt`

# Reproducing the main banner

```bash
# From repo root, requires $OPENROUTER_API_KEY
bash /path/to/agent-skills/skills/terminal-poster/scripts/generate.sh \
  scripts/banner/banner-prompt.txt \
  assets/banner.png
```

Costs ~$0.01, takes ~30 seconds.

# Reproducing a tier banner

```bash
bash /path/to/agent-skills/skills/terminal-poster/scripts/generate.sh \
  scripts/banner/tier-infrastructure-prompt.txt \
  assets/tier-infrastructure.png
```

# Reproducing a skill banner

```bash
bash /path/to/agent-skills/skills/terminal-poster/scripts/generate.sh \
  skills/doc-sync/assets/banner-prompt.txt \
  skills/doc-sync/assets/banner.png
```

# Known quirks

🟡 **JPEG-as-PNG:** Nano Banana Pro sometimes returns JPEG even when you write to `.png`. The generator script warns you but doesn't auto-rename. Sniff magic bytes (`xxd | head -1`) and rename if needed.

🟡 **Text-rendering drift:** the model can drop, duplicate, or garble labels. If a regeneration has spelling errors, tighten the prompt with:
- "the word X must appear in the image exactly once"
- "do not duplicate any label"
- "render text outside the card, not inside"

Don't try to fix small text errors by upscaling — regenerate with a tighter prompt instead.

# Design system reference

See [`../../AGENTS.md`](../../AGENTS.md) section "Imagery & Banners" for the palette, style rules, and step-by-step process for adding a banner to a new skill.
