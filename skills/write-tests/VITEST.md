# Vitest specifics (TypeScript, React, Node)

## Layers

| Flow | Drive it with | Assert with |
|---|---|---|
| Pure logic: reducers, parsers, date and music math | call it with a table of inputs (`test.each`) | literal expected values |
| React component or hook | `render`/`renderHook` from Testing Library, with the real providers and data layer | text and roles on screen, stored state, requests sent |
| HTTP route | the app over HTTP (`supertest`, or `app.listen(0)` and `fetch`) with a real database | status, body, rows written |
| Database module | a real database (see Database) | rows read back through the module's own API |
| CLI or script | the exported `run(argv)` in-process; at most one spawned smoke test | exit code, output when the output is the product, files written |
| Visual layout | Storybook and Chromatic, not Vitest | snapshots |

`vi.mock` only the network boundary: the API client module, an SDK such as Stripe, the mail sender, and `fetch`. Never `vi.mock` or `vi.spyOn` your own modules to check that they were called. Mocking your own modules is the change-detector pattern in its TypeScript form.

## Environment: `node` by default

jsdom setup costs about 0.5 s per test file. One 49-file client project spent 24 s of summed time on it locally (54 s on CI) against 5 s of actual tests. Run in `node` by default and opt in per file:

```ts
// vitest.config.ts: one project (or the whole config) with node as the default
test: { environment: 'node' }

// first line of a file that renders React or needs a browser global
// @vitest-environment jsdom
```

- **To find which files need jsdom**, copy the config and set `environment: 'node'`, run it, and the files that fail are your list. The `--environment` CLI flag does **not** override `environment` inside `test.projects`, so the flag silently proves nothing there.
- A test that imports a page module only to test one function in it pulls in the whole page, and anything that touches `window` at import time. Move the function to its own module.
- A test that needs only `localStorage` can stub it with a small in-memory `Storage` (`vi.stubGlobal('localStorage', memoryStorage())`) instead of paying for a DOM.
- `happy-dom` sets up faster than jsdom but is less complete. Measure before switching, and keep jsdom for any file that breaks.

## Time: fake timers, never sleeps

```ts
beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

await vi.advanceTimersByTimeAsync(1_000); // runs timers, awaits the promises they settle
vi.setSystemTime(new Date('2026-03-08T09:00:00Z')); // pin "now" for date logic
vi.useFakeTimers({ toFake: ['Date'] }); // only Date, when the code reads Date.now() but awaits real I/O
```

- **Assert exact values.** A real `sleep(100)` with ±30 ms tolerance is slow and still flaky.
- **Inject a clock or scheduler** (`now: () => number`, `setTimer`) into code with scheduling logic. That beats global fakes, and the test reads as the scenario.
- **Pin `new Date()`** in any code that buckets by day or month. Otherwise the test fails at a month boundary in UTC.
- **Pin the time zone.** Set `TZ` in the config's `test.env`, or pass zones explicitly, and test daylight-saving edges as literal cases.
- **React and fake timers:** advance the clock inside `act()`, then assert synchronously. `waitFor` and `findBy*` poll on timers, so under fake timers they need `vi.useFakeTimers({ shouldAdvanceTime: true })`.
- **Polling for an animation frame** costs seconds where frames are throttled. Feed the frame or drive the reducer directly.

## Suite-wide guards

```ts
// vitest.config.ts
test: {
  setupFiles: ['./test/setup.ts'],
  restoreMocks: true, // spies and vi.fn implementations reset between tests: no order dependence
  unstubGlobals: true,
  unstubEnvs: true,
}

// test/setup.ts: an unmocked request fails instead of waiting on a live service
import nock from 'nock'; // v14+ also intercepts native fetch
nock.disableNetConnect();
nock.enableNetConnect((host) => host.startsWith('127.0.0.1') || host.startsWith('localhost'));
```

If the project already uses MSW, `server.listen({ onUnhandledRequest: 'error' })` does the same. Database connections are plain TCP, so neither one gets in their way.

## Fixed per-file cost

Every file gets a fresh module graph and a fresh environment. Vitest prints the split at the end of a run: `Duration 14.08s (transform 6s, setup 0ms, import 12s, tests 27s, environment 25s)`. The phases are summed across workers. When `environment + import` rivals `tests`, fix the fixed cost before chasing slow tests.

- **Environment:** see above.
- **Import:**
  - Import the smallest module that holds the behavior, not a barrel or a page.
  - Put heavy libraries that only some paths need behind a dynamic `import()` in the app code.
- **The slowest file sets the floor for wall time,** because a file runs on one worker. Split a file whose duration approaches the whole run's wall time.
- **Subprocesses:**
  - Test the exported function in-process.
  - Build a shared fixture once in `beforeAll`, for example one git repository with one file per scenario rather than `git init` per test.
  - A whole TypeScript compile (`tsc`, schema generation) belongs in a CI step that regenerates and runs `git diff --exit-code`, not in a test.
- **External corpora and sibling repositories:** gate them with `test.skipIf(!fs.existsSync(dir))` or an opt-in env flag (`describe.runIf(process.env.CORPUS)`) so the report says *skipped*. An early `return` reports a pass that checked nothing.
- **Fixtures:**
  - Write outputs to `fs.mkdtemp(os.tmpdir())` or keep them in memory. Tests that write tracked fixture files race other files in parallel and dirty the checkout.
  - Use the shortest input that proves the behavior: 0.25 s of audio, not 2 s; 55 frames, not 320.
- **Pool knobs:** `pool: 'threads'` starts faster than the default `forks`, and `isolate: false` skips the per-file re-import for pure-logic projects. Both trade safety (native modules, module-level state) for speed. Measure, and apply per project.

## Database

- Use a real database, with an isolated schema per worker. Derive the schema name from `process.env.VITEST_POOL_ID` and set it as `search_path`. Alternatively, open a transaction per test and roll it back.
- Run migrations once per worker or in `globalSetup`, never per test.
- Let the test own its connection. A module-level static pool that tests cannot replace pushes people into faking SQL text or reading source files, which are both change detectors.

## Measuring

```sh
vitest run --reporter=default --reporter=json --outputFile.json=report.json
scripts/vitest-stats.py report.json            # serial cost, median, slow tail, slowest files and tests
vitest run --no-file-parallelism --maxWorkers=1  # the honest serial number
```

In CI, add `--reporter=junit --outputFile.junit=junit.xml`, upload the report as an artifact, and append `scripts/vitest-stats.py report.json --markdown` to `$GITHUB_STEP_SUMMARY`. Set `slowTestThreshold` in the config so the default reporter flags slow tests as they are written.

## Pruning with coverage

Vitest cannot attribute coverage to a single test, so `scripts/vitest-cov.py` runs each test file alone with v8 coverage (`@vitest/coverage-v8`, the same version as `vitest`). It is the per-file version of the method in [PRUNING.md](PRUNING.md):

```sh
PROCS=4 scripts/vitest-cov.py run base.json --all            # baseline; ~1 min for 180 files on 8 cores
scripts/vitest-cov.py unique base.json --timing report.json  # files whose every line is covered elsewhere

scripts/vitest-cov.py run before.json a.test.ts b.test.ts    # before editing these files
#   ...delete, merge, shrink...
scripts/vitest-cov.py run after.json a.test.ts b.test.ts     # deleted files drop out
scripts/vitest-cov.py lost base.json before.json after.json  # must print "0 LOST from the suite"
```

- Change only tests between `before` and `after`; an edit to app code shifts line numbers.
- The `run` command refuses a file vitest did not run, such as a path outside the include globs. Without that check, it would record an empty coverage report as "covers nothing".
- `unique` shows coverage-redundant files. That gives you candidates, not a verdict: line coverage cannot see assertion strength, so negative-path and authorization tests often show 0 unique lines and are still needed.
- Finish with `scripts/vitest-cov.py compare base.json final.json` over the whole suite, then compare a serial run of both commits back to back.
