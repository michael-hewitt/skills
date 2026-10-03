<?php

declare(strict_types=1);

namespace TestSuiteTools;

use PHPUnit\Event\Test\Finished;
use PHPUnit\Event\Test\FinishedSubscriber;
use PHPUnit\Event\Test\PreparationStarted;
use PHPUnit\Event\Test\PreparationStartedSubscriber;
use PHPUnit\Runner\Extension\Extension;
use PHPUnit\Runner\Extension\Facade;
use PHPUnit\Runner\Extension\ParameterCollection;
use PHPUnit\TextUI\Configuration\Configuration;

/**
 * Records, per test, the application lines it executed (pcov), its wall and CPU
 * time, and whether it was the first test of its process (which also pays for
 * migrate:fresh). Writes one JSON line per test to $LINECOV_DIR/<pid>.jsonl:
 * {id, first, time, cpu, cov: {"app/...php": [lines], "resources/views/...blade.php": [...]}}.
 * Inactive unless LINECOV_DIR is set and pcov is loaded; LINECOV_ROOT is the repo root.
 */
final class LineCoverageExtension implements Extension
{
    public static float $started = 0.0;

    public static float $cpuStarted = 0.0;

    /** @var resource|null */
    public static $out = null;

    public static string $root = '';

    public static bool $first = true;

    /** @var array<string, string|null> */
    public static array $keys = [];

    /**
     * app/ and routes/ files map to their repo path; a compiled Blade view maps to
     * its resources/views source (from the compiler's PATH footer). Anything else
     * (vendor views, framework files) is dropped.
     */
    public static function sourceKey(string $file): ?string
    {
        if (array_key_exists($file, self::$keys)) {
            return self::$keys[$file];
        }
        $key = null;
        if (str_starts_with($file, self::$root)) {
            $relative = substr($file, strlen(self::$root));
            if (str_starts_with($relative, 'app/') || str_starts_with($relative, 'routes/')) {
                $key = $relative;
            } elseif (str_starts_with($relative, 'storage/framework/views/')) {
                $contents = (string) @file_get_contents($file);
                if (preg_match('~/\*\*PATH (.+?) ENDPATH\*\*/~', $contents, $m) === 1) {
                    $source = (string) realpath($m[1]);
                    if (str_starts_with($source, self::$root.'resources/views/')) {
                        $key = substr($source, strlen(self::$root));
                    }
                }
            }
        }

        return self::$keys[$file] = $key;
    }

    public static function cpu(): float
    {
        $usage = getrusage();

        return $usage['ru_utime.tv_sec'] + $usage['ru_utime.tv_usec'] / 1e6
            + $usage['ru_stime.tv_sec'] + $usage['ru_stime.tv_usec'] / 1e6;
    }

    public function bootstrap(Configuration $configuration, Facade $facade, ParameterCollection $parameters): void
    {
        $dir = getenv('LINECOV_DIR');
        if (! is_string($dir) || $dir === '' || ! function_exists('pcov\\start')) {
            return;
        }

        // Under --parallel the coordinating process runs no tests; only its workers (PARATEST=1) record.
        if (getenv('PARATEST') === false && in_array('--parallel', $_SERVER['argv'] ?? [], true)) {
            return;
        }
        self::$root = rtrim((string) getenv('LINECOV_ROOT'), '/').'/';
        @mkdir($dir, 0777, true);
        self::$out = fopen($dir.'/'.getmypid().'.jsonl', 'ab');

        $facade->registerSubscribers(
            new class implements PreparationStartedSubscriber
            {
                public function notify(PreparationStarted $event): void
                {
                    \pcov\clear();
                    LineCoverageExtension::$started = hrtime(true) / 1e9;
                    LineCoverageExtension::$cpuStarted = LineCoverageExtension::cpu();
                    \pcov\start();
                }
            },
            new class implements FinishedSubscriber
            {
                public function notify(Finished $event): void
                {
                    \pcov\stop();
                    $elapsed = hrtime(true) / 1e9 - LineCoverageExtension::$started;
                    $cpu = LineCoverageExtension::cpu() - LineCoverageExtension::$cpuStarted;
                    $raw = \pcov\collect(\pcov\all);
                    \pcov\clear();
                    $lines = [];
                    $rootLength = strlen(LineCoverageExtension::$root);
                    foreach ($raw as $file => $hits) {
                        $executed = [];
                        foreach ($hits as $line => $hit) {
                            if ($hit > 0) {
                                $executed[] = $line;
                            }
                        }
                        if ($executed === []) {
                            continue;
                        }
                        sort($executed);
                        $relative = LineCoverageExtension::sourceKey($file);
                        if ($relative === null) {
                            continue;
                        }
                        $lines[$relative] = $executed;
                    }
                    $test = $event->test();
                    fwrite(LineCoverageExtension::$out, json_encode([
                        'id' => $test->id(),
                        'first' => LineCoverageExtension::$first,
                        'time' => round($elapsed, 4),
                        'cpu' => round($cpu, 4),
                        'cov' => $lines,
                    ], JSON_UNESCAPED_SLASHES)."\n");
                    LineCoverageExtension::$first = false;
                }
            },
        );
    }
}
