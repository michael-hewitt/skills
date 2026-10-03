<?php

/**
 * Remove Pest tests from files by their evaluable method name.
 *
 * Usage: php remove_tests.php <repo-root> < plan.json
 * plan.json: {"tests/Feature/Foo/BarTest.php": ["__pest_evaluable_it_does_x", ...], ...}
 *
 * A test whose name is listed is removed with its leading comments. A describe()
 * block left without tests is removed. A file left without tests is deleted
 * unless it declares functions/classes (reported as "kept-empty").
 * Prints a JSON report.
 */

declare(strict_types=1);

$root = rtrim($argv[1], '/');
require $root.'/vendor/autoload.php';

use PhpParser\Node;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\MethodCall;
use PhpParser\Node\Stmt;
use PhpParser\ParserFactory;

$plan = json_decode(stream_get_contents(STDIN), true, flags: JSON_THROW_ON_ERROR);
$parser = (new ParserFactory)->createForHostVersion();
$report = [];

function evaluable(string $code): string
{
    $code = str_replace('_', '__', $code);
    $code = '__pest_evaluable_'.str_replace(' ', '_', $code);

    return (string) preg_replace('/[^a-zA-Z0-9_\x80-\xff]/', '_', $code);
}

function rootCall(Node $expr): ?FuncCall
{
    while ($expr instanceof MethodCall) {
        $expr = $expr->var;
    }

    return $expr instanceof FuncCall && $expr->name instanceof Node\Name ? $expr : null;
}

function firstStringArg(FuncCall $call): ?string
{
    $arg = $call->args[0] ?? null;
    if (! $arg instanceof Node\Arg) {
        return null;
    }
    $value = $arg->value;
    if ($value instanceof Node\Scalar\String_) {
        return $value->value;
    }

    return null;
}

/**
 * @param  list<Stmt>  $stmts
 * @param  list<string>  $describing
 * @param  array<string, true>  $targets
 * @return array{remove: list<array{int,int}>, remaining: int, found: list<string>}
 */
function scan(array $stmts, array $describing, array $targets): array
{
    $remove = [];
    $remaining = 0;
    $found = [];
    foreach ($stmts as $stmt) {
        if (! $stmt instanceof Stmt\Expression) {
            continue;
        }
        $call = rootCall($stmt->expr);
        if ($call === null) {
            continue;
        }
        $fn = strtolower($call->name->toString());
        $desc = firstStringArg($call);
        if ($desc === null) {
            if (in_array($fn, ['it', 'test', 'describe'], true)) {
                $remaining++;
            }

            continue;
        }
        if ($fn === 'describe') {
            $closure = $call->args[1]->value ?? null;
            if ($closure instanceof Node\Expr\Closure || $closure instanceof Node\Expr\ArrowFunction) {
                $inner = scan($closure instanceof Node\Expr\Closure ? $closure->stmts : [], [...$describing, $desc], $targets);
                $found = [...$found, ...$inner['found']];
                if ($inner['remaining'] === 0 && $inner['found'] !== []) {
                    $remove[] = span($stmt);
                } else {
                    $remove = [...$remove, ...$inner['remove']];
                    $remaining += $inner['remaining'] > 0 ? 1 : 0;
                }
            }

            continue;
        }
        if ($fn !== 'it' && $fn !== 'test') {
            continue;
        }
        $description = $fn === 'it' ? 'it '.$desc : $desc;
        if ($describing !== []) {
            $description = sprintf(str_repeat('`%s` → ', count($describing)).'%s', ...[...$describing, $description]);
        }
        $name = evaluable($description);
        if (isset($targets[$name])) {
            $remove[] = span($stmt);
            $found[] = $name;
        } else {
            $remaining++;
        }
    }

    return ['remove' => $remove, 'remaining' => $remaining, 'found' => $found];
}

/** @return array{int,int} */
function span(Stmt $stmt): array
{
    $start = $stmt->getStartFilePos();
    foreach ($stmt->getComments() as $comment) {
        $start = min($start, $comment->getStartFilePos());
    }

    return [$start, $stmt->getEndFilePos() + 1];
}

foreach ($plan as $relative => $names) {
    $path = $root.'/'.$relative;
    if (! is_file($path)) {
        $report[$relative] = ['status' => 'missing'];

        continue;
    }
    $code = file_get_contents($path);
    $ast = $parser->parse($code);
    $targets = array_fill_keys($names, true);
    $result = scan($ast, [], $targets);
    $missing = array_values(array_diff($names, $result['found']));

    if ($result['remaining'] === 0) {
        $declares = false;
        foreach ($ast as $stmt) {
            if ($stmt instanceof Stmt\Function_ || $stmt instanceof Stmt\ClassLike) {
                $declares = true;
            }
        }
        if (! $declares) {
            unlink($path);
            $report[$relative] = ['status' => 'deleted', 'removed' => count($result['found']), 'missing' => $missing];

            continue;
        }
    }

    $spans = $result['remove'];
    usort($spans, fn ($a, $b) => $b[0] <=> $a[0]);
    foreach ($spans as [$start, $end]) {
        // Swallow the rest of the line (newline) after the statement.
        while ($end < strlen($code) && ($code[$end] === ' ' || $code[$end] === "\t")) {
            $end++;
        }
        if ($end < strlen($code) && $code[$end] === "\n") {
            $end++;
        }
        // Swallow indentation before the statement.
        while ($start > 0 && ($code[$start - 1] === ' ' || $code[$start - 1] === "\t")) {
            $start--;
        }
        $code = substr($code, 0, $start).substr($code, $end);
    }
    $code = (string) preg_replace("/\n{3,}/", "\n\n", $code);
    $code = (string) preg_replace("/\{\n\n+/", "{\n", $code);
    $code = (string) preg_replace("/\n\n+(\s*\}\);)/", "\n$1", $code);
    file_put_contents($path, $code);
    $report[$relative] = [
        'status' => $result['remaining'] === 0 ? 'kept-empty' : 'edited',
        'removed' => count($result['found']),
        'remaining' => $result['remaining'],
        'missing' => $missing,
    ];
}

echo json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
