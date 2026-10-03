# Pruning a suite without losing coverage

The scripts below are for PHPUnit/Pest. For Vitest, `scripts/vitest-cov.py` records coverage per test file and runs the same remove-only-what-coverage-allows check; see [VITEST.md](VITEST.md#pruning-with-coverage).

## 1. Record per-test coverage and time

Standard coverage reports merge tests together; you need, for every test, the set of lines it executed. For PHP, `scripts/LineCoverageExtension.php` is a PHPUnit extension that uses pcov to write one JSON line per test: `{id, first, time, cpu, cov: {file: [lines]}}`. It keeps `app/`, `routes/` and compiled Blade views (mapped back to `resources/views/*.blade.php` through the compiler's `PATH` footer), because templates hold logic too.

**Requirements:** pcov for the project's PHP (macOS/Homebrew: `brew tap shivammathur/extensions && brew install shivammathur/extensions/pcov@8.4`; set `PCOV_SO` if it lives elsewhere), Python 3 with numpy for the analysis scripts, and optionally Excimer (`excimer@8.4`, `EXCIMER_SO`) for `profile.sh`. The scripts write their generated PHPUnit configs and results outside the checkout.

```sh
scripts/run-cov.sh <repo-root> <out-dir> [path]    # parallel run (PROCS=7); <out-dir>/cov/*.jsonl + junit.xml
scripts/cov-files.sh <out.json> <files...>         # serial run of some files; union of covered lines
scripts/run-timing.sh <repo-root> <out-dir>        # parallel run, JUnit timings only
scripts/run-serial.sh <repo-root> <out-dir>        # whole suite in one process, the honest serial number
scripts/profile.sh <out-prefix> <files...>         # Excimer wall-clock profile; rank with topframes.py
scripts/junitstats.py <junit.xml>                  # serial sum, slow tail, slowest files and tests
```

Run long measurements in a separate worktree pinned to a commit, so you can keep editing while a run takes an hour.

## 2. Inventory and tag tests

- `scripts/list_tests.php <root> < files` lists every Pest test (file, method name, description, lines, body).
- `scripts/categorize.py` tags harmful patterns by name and body (tautological model tests, enum listings, config echoes, "no longer exists" guards, source reading, one-shot migrations, internal mocks). The regexes are a first pass; read a random sample before trusting them, and spare names that state a condition ("defaults X **for** Y" is logic).

## 3. Remove only what coverage allows

`scripts/analysis.py` loads the coverage (`covdb.py`) and answers: *if this set of tests goes, which lines lose their last covering test?* Remove candidates greedily, slowest first, and keep any test whose removal would lose a line:

```python
A = Analysis(load(covdir))
for key, idx in candidates:            # idx = the test's dataset cases
    if len(A.lost_if_removed(idx)) == 0:
        A.remove(idx); plan[file].append(method)
```

Apply with `scripts/remove_tests.php <root> < plan.json`. It removes Pest tests by method name, with their comments, drops emptied `describe()` blocks, and deletes files left with no tests unless they declare helpers (check those helpers' callers, then delete). Run the formatter, run every edited file, and commit one category per commit.

A test that matches a harmful pattern but is the only coverage of some line points at either untested code (move the assertion into a feature test) or dead code (delete the code, with approval).

## 4. Redundancy beyond the patterns

A greedy pass over the whole suite usually shows most tests add no line coverage of their own. That is an upper bound, not a plan: line coverage cannot see assertion strength, so negative-path, authorization and value-checking tests look redundant. Review such tests by flow: keep one or two feature tests per flow that carry every distinct assertion, then delete the lower-layer tests that restate them. Mutation testing (`pest --mutate`) on the flow's classes, before and after, proves the replacement is as strong.

### Consolidating by flow (parallel agents)

What worked on a 12,600-test Laravel suite (12,611 → 5,679 test cases, no line of coverage lost):

- Split the suite into flows (one domain's Livewire/Filament/service/listener/mail tests together) and give each flow to one agent in its own git worktree, with a shared written brief. The brief: combine related tests that rebuild the same fixture into one scenario (≤ ~6 behaviors, one story), keep one or two real-stack tests per flow and fold in lower-layer assertions, delete harmful tests, shrink fixtures, turn long datasets over expensive fixtures into loops, keep every negative/authorization case and every distinct numeric case.
- Each agent proves its own change: `scripts/cov-files.sh before.json <files>` before editing, again after, then `COV_BASELINE=<full-run cov dir> scripts/cov-global.py before.json after.json <files>` must report `0 LOST from the suite` (a line the flow stops covering is fine if another test still covers it).
- Ask each agent for a list of judgment calls (tests deleted without an equivalent, fixtures changed, scenarios narrowed) and pass them to the human reviewer.
- Merge by cherry-picking each agent's commit, run its files, then run the whole suite: parallel agents can collide in ways no single agent sees. Seen in practice: two agents adding a global Pest helper with the same name (fatal "Cannot redeclare"), agents overwriting each other's temp files (give each a unique prefix), a test-support class made `final` that broke `Facade::shouldReceive` elsewhere.

## 5. Verify

Rerun the full suite with coverage (`scripts/run-cov.sh`) and compare with `scripts/cov-compare.py <baseline cov dir> <final cov dir>`. Expect a small difference only from nondeterministic code (network, time, randomness, ordering); investigate anything else. Then time a true serial run of both commits back to back (`scripts/run-serial.sh`), with nothing else running.
