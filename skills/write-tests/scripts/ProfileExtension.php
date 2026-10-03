<?php

declare(strict_types=1);

namespace TestSuiteTools;

use PHPUnit\Runner\Extension\Extension;
use PHPUnit\Runner\Extension\Facade;
use PHPUnit\Runner\Extension\ParameterCollection;
use PHPUnit\TextUI\Configuration\Configuration;

/**
 * Samples wall-clock stacks across a whole Pest run with Excimer and writes them,
 * in collapsed-stack format, to $PROFILE_OUT.<pid> when the process exits.
 * Inactive unless PROFILE_OUT is set and the Excimer extension is loaded.
 */
final class ProfileExtension implements Extension
{
    private static ?\ExcimerProfiler $profiler = null;

    public function bootstrap(Configuration $configuration, Facade $facade, ParameterCollection $parameters): void
    {
        $out = getenv('PROFILE_OUT');

        if (! is_string($out) || $out === '' || ! class_exists(\ExcimerProfiler::class)) {
            return;
        }

        // Formatting a long run's samples needs more than the suite's usual memory cap.
        ini_set('memory_limit', '4G');

        self::$profiler = new \ExcimerProfiler;
        self::$profiler->setPeriod((float) (getenv('PROFILE_PERIOD') ?: 0.002));
        self::$profiler->setEventType(EXCIMER_REAL);
        self::$profiler->start();

        register_shutdown_function(static function () use ($out): void {
            self::$profiler?->stop();
            file_put_contents($out.'.'.getmypid(), self::$profiler?->getLog()->formatCollapsed());
        });
    }
}
