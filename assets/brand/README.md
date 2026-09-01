# Brand assets (placeholder)

Generated from the only MiTY logo files available in the project (`docs/Mity logo.png`, 79×71px, and `docs/Mity logo with text.png`, 273×79px) — both far below the resolution `home-assistant/brands` actually wants, so these are **upscaled placeholders**, not submission-ready assets. They exist so the integration has *something* branded now, and so the eventual `home-assistant/brands` PR has a clear shape to fill in once a real high-resolution logo exists.

| File | Size | Source |
|---|---|---|
| `icon.png` | 256×256 | `Mity logo.png`, padded to square, upscaled |
| `icon@2x.png` | 512×512 | same, upscaled further |
| `logo.png` | 442×128 | `Mity logo with text.png`, upscaled |
| `logo@2x.png` | 512×148 | same, upscaled further (width-capped at 512 per `home-assistant/brands` convention) |

**Before actually submitting to `home-assistant/brands`**: replace these with exports from a real high-resolution source (vector if possible — the design tool the logo was originally made in, not a re-upscale of these files). Upscaling a 79×71 source can only get so sharp; a proper submission should start from something at least 512×512 natively. See [docs/HACS_RELEASE_CHECKLIST.md](../docs/HACS_RELEASE_CHECKLIST.md) Section 4 for the full submission process.
