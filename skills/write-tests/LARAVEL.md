# Laravel and Pest specifics

## Layers

| Flow | Drive it with | Assert with |
|---|---|---|
| HTTP route | `$this->actingAs($user)->post(route('x'), [...])` | `assertRedirect`, `assertSee`, `assertDatabaseHas`, `Mail::assertSent` |
| Livewire component | `Livewire::actingAs($user)->test(Component::class)->set(...)->call(...)` | `assertHasNoErrors`, `assertSee`, persisted records |
| Filament action/page | `Livewire::test(EditRecord::class, ['record' => $id])->callAction(...)` | notifications, persisted records |
| Console command | `$this->artisan('name', [...])->assertSuccessful()` | persisted records, output only when it is the product |
| Job / listener | dispatch the domain event or call the entry point that queues it (`QUEUE_CONNECTION=sync`) | its effects, not `shouldReceive` |

Use `Mail::fake()`, `Notification::fake()`, `Event::fake([OnlyThis::class])`, `Queue::fake()` and `Http::fake()` for boundaries; never `mock(App\Services\...)`.

## Suite-wide guards in `tests/TestCase.php`

```php
protected function setUp(): void
{
    parent::setUp();

    Http::preventStrayRequests(); // an unfaked request throws instead of waiting on a live service
}
```

One project's "slow tests" were mostly observers geocoding addresses through a live API; this one line cut the slowest files by 10–15×.

## Per-test fixed cost

Every Laravel test boots a new application and, with `RefreshDatabase`, opens a new database connection. Profile a run of trivial tests (`scripts/profile.sh`, then `scripts/topframes.py <prefix>.* --match 'Provider::|createApplication'`) and look under `TestCase::setUp`. Fixes that worked:

- **`WithCachedConfig` and `WithCachedRoutes`** (Laravel 12+): add both traits to `TestCase`. Config and routes load once per process.
- **macOS collation**: under a UTF-8 `LC_COLLATE`, `glob()` sorts through a slow `strcoll()`; package providers glob the migrations directory on every boot. `setlocale(LC_COLLATE, 'C');` at the top of `tests/Pest.php` cut boot CPU by ~40%.
- **Blade Icons manifest**: without `icons:cache` it scans every SVG on each boot. Rebind `BladeUI\Icons\IconsManifest` in `TestCase::createApplication()` (after `RegisterProviders`) to a manifest file written once per process in a temp directory.
- **Database session reuse** (PostgreSQL/MySQL): Laravel reuses one PDO only for in-memory SQLite. Override `beginDatabaseTransaction()` in your RefreshDatabase trait: hand a parked PDO to the new connection before `beginTransaction()`, and after the teardown `rollBack()` park the PDO only if it has no open transaction and `RefreshDatabaseState::$migrated` is still true. Hold no reference while the test runs, or a test that purges its connection leaves a session with an open transaction holding locks, and the next `migrate:fresh` deadlocks.
- **Spatie package tools** glob the migrations directory on every boot to name `vendor:publish` targets. After `RegisterProviders`, empty each `PackageServiceProvider`'s `package->migrationFileNames` (tests never publish; check the package doesn't run its migrations itself).
- **Filament discovery**: Filament ignores its component cache in the console, so it walks `app/Filament` on every boot. Extend the container's `files` binding with a `Filesystem` subclass that memoizes `allFiles()` for directories under `app/` for the life of the process.
- **Commands and listeners**: bind a `Console\Kernel` subclass whose `findCommands()` memoizes the listing (override `shouldDiscoverCommands()` to return true: the framework discovers only for its own class), and point `APP_EVENTS_CACHE` at a per-process file written after the first boot, as `event:cache` does.
- Keep these support classes non-`final`: `Artisan::shouldReceive()` and `File::shouldReceive()` mock whatever class the facade resolves to.

Together these cut the fixed cost of every test several-fold. Working versions: `tests/TestCase.php`, `tests/StrictRefreshDatabase.php`, `tests/ApplicationSourceFilesystem.php` and `tests/ConsoleKernel.php` in `accsTechnology/classicalchristian-platform`.

## Measuring

- `pest --parallel --log-junit junit.xml` gives per-test wall time. Sum it for the serial cost; look at both the slow tail (tests over 1s) and the median (the fixed cost).
- Wall time far above CPU time means waiting: network, `sleep`, or locks.
- Herd's PHP ignores `PHP_INI_SCAN_DIR`; load pcov or Excimer into ParaTest workers with `PHPRC=/path/to/extra.ini`.
