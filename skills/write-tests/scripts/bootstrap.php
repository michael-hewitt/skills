<?php

// PHPUnit bootstrap for the write-tests scripts: the project's autoloader plus this directory's extensions.
require getcwd().'/vendor/autoload.php';
require __DIR__.'/LineCoverageExtension.php';
require __DIR__.'/ProfileExtension.php';
