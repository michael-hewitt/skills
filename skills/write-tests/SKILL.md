---
name: write-tests
description: Decide which tests to write, at which layer, and which to delete, so a suite proves behavior without creeping in size or run time. Use when writing or adding tests for a feature or bug fix, adding a regression test, reviewing tests in a diff, deciding between unit, feature and browser tests, or pruning, consolidating or speeding up a slow or bloated test suite.
---

# Write Tests

A test earns its place by failing when behavior breaks and staying green when behavior holds. Every test also costs run time and upkeep, so the goal is the fewest tests that would catch real regressions. This skill decides what to test, where, and what to remove; for the red → green loop itself, use a `tdd` skill if one is installed. Where the project has its own testing rules (`AGENTS.md`, a framework testing skill such as `pest-testing`), follow them for conventions and commands; this skill supplies the method.

## Before writing a test

1. **Find the test that already drives this flow.** Search for the route, component, command, or job name. If a feature test drives it, add a scenario or an assertion there. Create a new file only for a flow nothing drives yet.
2. **Pick the scenario.** Choose a medium-to-hard case that exercises the interesting branches, not the simplest input that passes. Add the unhappy path and the authorization boundary as their own scenarios; they often run the same lines as the happy path but assert different behavior.
3. **Pick the layer**, in this order of preference:
   - **Feature test through the real stack** (default): HTTP route, UI component, admin action, console command, or job, with real services and a real database. One of these replaces the separate service, listener, job, mail, and observer tests it passes through.
   - **Unit test**: only for pure logic with many input combinations (pricing, proration, date math, parsers). Table-driven, with literal expected values.
   - **Browser test**: only for critical user journeys and behavior that needs a real browser. They are the slowest layer.
4. **Assert observable outcomes**: the response, rendered output, persisted records, mail and notifications sent, events dispatched, calls to external adapters. In a web app, the database is an output of the system; checking the saved record is fine. Checking private state or internal calls is not.

A bug fix still starts with a failing test, usually as one more scenario in the existing feature test.

## Never write these

- **Tautological tests** pass by construction: reading back what a factory or fixture wrote, asserting a relationship method returns a relationship, casts, defaults, enum cases or labels, config returning config, an expected value computed the way the code computes it, a column or method that "no longer exists".
- **Change detectors** break on harmless edits: reading source, docs, or CI files and asserting on their text, pinning file hashes, asserting long exact copy, mocking your own classes to assert they were called.
- **Network access**: mock external adapters (payments, email providers, third-party APIs, geocoding) and time only. Make the suite refuse stray HTTP requests so an unmocked integration fails instead of waiting on a live service. A deliberate live-integration test opts in explicitly.

## Keep it fast

- Combine related tests that build the same fixture: when several tests set up the same scenario and each checks one facet, make them one test named for the scenario, with all the assertions. Keep each test one story (roughly six behaviors at most); do not merge unrelated scenarios just because their setup looks alike. Setup, not assertions, is where suite time goes.
- Create the fewest records that prove the behavior. A limit of 1,000 needs 1,001 rows in one test, not in every test that lists records.
- Never sleep or poll; use fake clocks, fake queues, and synchronous drivers. The exception is a test of genuine concurrency (two processes contending for a database lock), which may poll the database briefly.
- Watch the fixed per-test cost (app boot, database connection, seeding). It is paid by every test, so it often matters more than any single slow test. See [LARAVEL.md](LARAVEL.md) for the Laravel/Pest fixes and [VITEST.md](VITEST.md) for Vitest (TypeScript, React, Node): `node` instead of jsdom by default, fake timers, and the network guard.

## Pruning an existing suite

Use coverage, not judgment alone, so deletions never lose coverage. See [PRUNING.md](PRUNING.md) (PHP tooling; for Vitest, the per-file version in [VITEST.md](VITEST.md#pruning-with-coverage)): record per-test line coverage and timings, delete harmful-pattern tests only where every line they cover is covered by another test, and review coverage-redundant tests by hand before removing them. Line coverage cannot see assertion strength: a negative-path test often covers no line of its own and is still needed.

## Reviewing tests in a diff

Flag: a new test file for a flow an existing test drives; the same flow tested at several layers; any pattern under "Never write these"; bulk fixtures; sleeps; missing unhappy-path or authorization scenarios.
