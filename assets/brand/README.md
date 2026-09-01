# Brand assets (placeholder)

`icon.png`/`icon@2x.png` and `logo.png`/`logo@2x.png` use the full "MiTY TRE" text lockup, by deliberate choice — `icon.png` was regenerated from `icon@2x.png` (not from the original mark-only source) so both icon sizes show the same design, just at different resolutions. Note that at the small sizes Home Assistant actually renders icons at in most UI contexts (often 24–48px), the tagline text will likely be illegible — an inherent tradeoff of that choice, not a defect in the file.

Still **not submission-quality**: the underlying source material is low-resolution (the original project logo files were 79×71px and 273×79px), so all four files here show visible softening from upscaling, most noticeably in `icon@2x.png`/`icon.png`'s small text. They exist so the integration has *something* branded now, and so the eventual `home-assistant/brands` PR has a clear shape to fill in once a genuinely high-resolution (ideally vector) source exists.

| File | Size |
|---|---|
| `icon.png` | 256×256 |
| `icon@2x.png` | 512×512 |
| `logo.png` | 442×128 |
| `logo@2x.png` | 512×148 (width-capped at 512 per `home-assistant/brands` convention) |

**Before actually submitting to `home-assistant/brands`**: replace these with exports from a real high-resolution source (vector if possible — the design tool the logo was originally made in, not a re-upscale of these files). See [docs/HACS_RELEASE_CHECKLIST.md](../docs/HACS_RELEASE_CHECKLIST.md) Section 4 for the full submission process.
