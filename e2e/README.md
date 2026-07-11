# ChatMoney E2E tests (Playwright)

End-to-end tests that drive the real Next.js frontend in a browser. The FastAPI
backend (Supabase + Google Gemini) is **mocked** at the network layer, so these
tests need **no secrets**, run fast, and are deterministic.

## How it works

- `playwright.config.ts` starts the frontend (`npm run dev` in `../frontend`)
  before the tests and stops it after. `NEXT_PUBLIC_API_URL` is set to a dummy
  `http://localhost:8000` — nothing actually listens there.
- `tests/support/mockApi.ts` exports `mockBackend(page, overrides?)`, which uses
  Playwright's `page.route()` to intercept every request to
  `localhost:8000` and reply with fixed JSON matching the backend's response
  shapes (`frontend/lib/types.ts` / `backend/schemas/models.py`). Pass
  `overrides` to simulate custom data or error statuses per test.
- Specs live in `tests/*.spec.ts`. `app.spec.ts` and `balance.spec.ts` are
  working examples; `flows.blueprint.spec.ts` holds skipped templates for the
  Chat / Dashboard / Advisor flows — copy the pattern and remove `.skip` to add
  coverage.

## Run locally

This is a self-contained npm project (its own `package.json`). First install the
frontend deps once so the dev server can boot, then run the tests:

```bash
cd frontend && npm install       # once, so `next dev` can run
cd ../e2e
npm install
npx playwright install chromium  # one-time browser download
npm test                         # headless run (auto-starts the frontend)
```

Useful variants:

```bash
npm run test:ui        # interactive Playwright UI mode
npm run test:headed    # watch a real browser
npm run report         # open the HTML report from the last run
```

## CI

`.github/workflows/e2e.yml` runs this suite on every push and pull request:
install frontend deps → install e2e deps → install the Chromium browser → run
the tests. The HTML report is uploaded as a build artifact (`playwright-report`)
so failures can be inspected from the Actions run. No secrets are configured
because the backend is mocked.

## Adding a test

1. Create `tests/<feature>.spec.ts`.
2. In `beforeEach`, call `await mockBackend(page)` (add `overrides` if the test
   needs specific data).
3. `await page.goto("/")`, drive the UI with locators (prefer roles/text), and
   assert on the result.
