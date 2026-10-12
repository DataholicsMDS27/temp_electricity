# Verification

## Automated checks

- TypeScript checking and the production Vite build pass (`npm run build`).
- Four backend contract tests pass (`.venv/bin/python -m unittest backend.test_contract`): deterministic Ontario-wide batches, valid temperature extremes and midnight hours, invalid-input rejection, explicit unsupported FSAs, and invalid-provider-output handling.
- Live API/map join verification passes for 520 FSAs with a -40 °C, weekend, 23:00–00:00 scenario (`npm run verify`).
- Dependency installation audit reports zero known npm vulnerabilities after updating MapLibre to 6.13.0.

## Browser checks

Verified in the Codex in-app browser at requested 1440×900 and 1280×800 desktop sizes (browser zoom can change the effective CSS viewport):

- Temperature slider and numeric entry; weekday/weekend; successful FastAPI response and hourly customer units.
- Hour wheel scrolling, keyboard navigation, previous/next controls, and midnight wrapping.
- Daylight night/light-map boundaries at 18:00 and 06:00, plus dawn/day/sunset/night background states.
- FSA search, polygon click selection, persistent customer details, province reset, and hover inspection.
- Previous scenario stays attached to displayed values after input edits.
- Information dialog, initial focus and Escape dismissal.
- Production-build map worker, basemap and prediction flow, with no browser console errors in the production smoke check.
- Visual checks: typography and number alignment, solid theme contrast, panel spacing, interval-wheel alignment, geographic label density, legend consistency, and accessible Predict-button placement.
- Desktop-only scope; narrow-screen layout is a fallback, not a verified mobile deliverable.

Screenshots are saved locally in `artifacts/light-desktop.jpg`, `artifacts/dark-desktop.jpg`, and `artifacts/daylight-desktop.jpg` (ignored from source control).

## Intentional limitations

The prediction provider is a synthetic demonstration; no trained model or observed consumption data is included. Confirm the training timezone, reconcile consumption FSAs against 2021 census geography, and calibrate the fixed legend before connecting the real model. External basemap services are used for detailed context; the app bundles a simpler geographic fallback. MapLibre's rendering bundle produces a Vite chunk-size advisory, without preventing the build.
