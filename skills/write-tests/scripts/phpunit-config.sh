#!/bin/zsh
# Usage: phpunit-config.sh <repo-root> <out.xml> [extension-class]
# Writes a copy of <repo-root>/phpunit.xml outside the checkout: relative paths made absolute,
# the tools' bootstrap (which loads this directory's PHPUnit extensions), an optional
# extension registered, and no memory cap (a long single-process run needs more than 1G).
set -eu
ROOT=${1:A}; OUT=$2; EXT=${3:-}
TOOLS=${0:A:h}
sed -e "s#bootstrap=\"vendor/autoload.php\"#bootstrap=\"$TOOLS/bootstrap.php\"#" \
    -e "s#<directory>\\([^/<][^<]*\\)</directory>#<directory>$ROOT/\\1</directory>#g" \
    -e 's#<ini name="memory_limit" value="[^"]*"/>#<ini name="memory_limit" value="-1"/>#' \
    -e "s#vendor/phpunit/phpunit/phpunit.xsd#$ROOT/vendor/phpunit/phpunit/phpunit.xsd#" \
    "$ROOT/phpunit.xml" > "$OUT"
if [[ -n "$EXT" ]]; then
    ext=${EXT//\\/\\\\}  # keep the namespace separator through sed
    sed -i '' -e "s#</phpunit>#    <extensions>\\n        <bootstrap class=\"$ext\"/>\\n    </extensions>\\n</phpunit>#" "$OUT"
fi
