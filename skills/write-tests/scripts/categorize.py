"""Tag each inventoried test with the #1491 harmful-pattern categories it matches.

Usage: python3 categorize.py inventory.jsonl > tagged.jsonl
"""

import json
import re
import sys

TAUTO_NAME = re.compile(
    r"\b(belongs? to|has many|has one|morph|casts?|can be created|defaults?|audit fields?|tracks audit|"
    r"nullable|factory|relationships?|fillable|uses uuid|uuid primary|timestamps|soft ?deletes?|"
    r"created_by and updated_by|table name|hidden attributes)\b",
    re.I,
)
ENUM_NAME = re.compile(r"\b(cases?|labels?|icons?|colou?rs?|values|every (type|case|value))\b", re.I)
GONE = re.compile(
    r"(hasColumn|hasTable|hasIndex|method_exists|property_exists|class_exists|function_exists|enum_exists)\([^;]*\)\s*\)?->\s*toBeFalse|"
    r"assertFalse\(\s*(Schema::)?(hasColumn|hasTable|method_exists|property_exists|class_exists)",
    re.I,
)
SOURCE_READ = re.compile(
    r"file_get_contents\(\s*(base_path|app_path|resource_path|database_path|config_path|dirname\(__DIR__|__DIR__)|"
    r"File::get\(\s*(base_path|app_path|resource_path|database_path)|hash_file\(|"
    r"(SKILL|AGENTS|CLAUDE|README)\.md|\.github/workflows|\.agents/skills",
)
CONDITIONAL = re.compile(r"\b(when|for|if|unless|only|except|after|before|based on|depending|while|until|resolves|computes|derives)\b", re.I)
CONFIG_ECHO = re.compile(r"expect\(\s*config\(")
INTERNAL_MOCK = re.compile(r"(mock|partialMock|spy)\(\s*\\?App\\|shouldReceive\(")


def tags_for(t):
    tags = []
    f, d, body = t['file'], t['description'], t['body']
    if f.startswith('tests/Feature/Models/') and TAUTO_NAME.search(d) and not CONDITIONAL.search(d):
        tags.append('tautological-model')
    if (f.startswith('tests/Feature/Enums/') or f.endswith('EnumTest.php')) and ENUM_NAME.search(d) and not CONDITIONAL.search(d):
        tags.append('enum')
    if CONFIG_ECHO.search(body):
        tags.append('config-echo')
    if GONE.search(body):
        tags.append('no-longer-exists')
    if SOURCE_READ.search(body):
        tags.append('source-reading')
    if f.startswith('tests/Feature/Migrations/') or re.search(r'/Backfill\w*Test\.php$', f) or \
            re.search(r'(MigrationTest|SchemaTest|RefactorTest)\.php$', f):
        tags.append('one-shot-migration')
    if re.search(r'FileMaker|WordPress|Wordpress|/Import\w*Test\.php$', f):
        tags.append('retired-import')
    if INTERNAL_MOCK.search(body):
        tags.append('internal-mock')
    return tags


for line in open(sys.argv[1]):
    t = json.loads(line)
    t['tags'] = tags_for(t)
    del t['body']
    print(json.dumps(t, ensure_ascii=False))
