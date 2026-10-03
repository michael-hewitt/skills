<?php

/**
 * Inventory every Pest test in the given files as JSON lines:
 * {file, name (evaluable), description, start, end, body}
 *
 * Usage: php list_tests.php <repo-root> <file>...  (or file list on stdin)
 */

declare(strict_types=1);

$root = rtrim($argv[1], '/');
require $root.'/vendor/autoload.php';

use PhpParser\Node;
use PhpParser\Node\Expr\FuncCall;
use PhpParser\Node\Expr\MethodCall;
use PhpParser\Node\Stmt;
use PhpParser\ParserFactory;

$files = array_slice($argv, 2);
if ($files === []) {
    $files = array_filter(array_map('trim', explode("\n", stream_get_contents(STDIN))));
}
$parser = (new ParserFactory)->createForHostVersion();

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

/**
 * @param  list<Stmt>  $stmts
 * @param  list<string>  $describing
 */
function walk(array $stmts, array $describing, string $file, string $code): void
{
    foreach ($stmts as $stmt) {
        if (! $stmt instanceof Stmt\Expression) {
            continue;
        }
        $call = rootCall($stmt->expr);
        if ($call === null) {
            continue;
        }
        $fn = strtolower($call->name->toString());
        $arg = $call->args[0] ?? null;
        $desc = ($arg instanceof Node\Arg && $arg->value instanceof Node\Scalar\String_) ? $arg->value->value : null;
        if ($desc === null) {
            continue;
        }
        if ($fn === 'describe') {
            $closure = $call->args[1]->value ?? null;
            if ($closure instanceof Node\Expr\Closure) {
                walk($closure->stmts, [...$describing, $desc], $file, $code);
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
        echo json_encode([
            'file' => $file,
            'name' => evaluable($description),
            'description' => $description,
            'start' => $stmt->getStartLine(),
            'end' => $stmt->getEndLine(),
            'body' => substr($code, $stmt->getStartFilePos(), $stmt->getEndFilePos() - $stmt->getStartFilePos() + 1),
        ], JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\n";
    }
}

foreach ($files as $file) {
    $code = (string) file_get_contents($root.'/'.$file);
    try {
        $ast = $parser->parse($code);
    } catch (Throwable $e) {
        fwrite(STDERR, "parse error {$file}: {$e->getMessage()}\n");

        continue;
    }
    walk($ast ?? [], [], $file, $code);
}
