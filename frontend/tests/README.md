# Frontend Tests

## Why tests live in `frontend/tests/`, not `tests/frontend/`

The short answer: Vite's module loading architecture forces it.

Vitest runs each test file in a Node.js worker process. That worker loads the
test file using Node's native `import()`, which requires a real filesystem path.
When a test file lives *outside* Vite's root directory (`frontend/`), Vite
generates a `/@fs/…` URL for it — a virtual URL that only Vite's HTTP server
understands. Node's `import()` can't resolve it, so the worker crashes before
a single test runs.

Keeping test files inside `frontend/` (even in a subdirectory) ensures Vite
can serve them as normal module URLs that Node resolves correctly.
The `frontend/tests/frontend/` path mirrors the `tests/backend/` pattern used
by the Python test suite, just rooted one level lower.

```
novotree.git/
├── tests/
│   └── backend/          ← Python / pytest tests
└── frontend/
    └── tests/
        └── frontend/     ← Vitest / React Testing Library tests  (here)
```

## Configuration

| File | Role |
|---|---|
| `frontend/vitest.config.ts` | Separate Vitest config — `vite build` is unaffected |
| `frontend/tests/setup.ts` | Global setup: loads `@testing-library/jest-dom` matchers |
| `frontend/tests/frontend/*.test.tsx` | Component tests |

Vitest is picked up automatically because it prefers `vitest.config.ts` over
`vite.config.ts` when both are present.

## How to run

```bash
cd frontend
npm test          # run all tests once (CI mode)
npx vitest        # watch mode — reruns on file changes (dev mode)
```
