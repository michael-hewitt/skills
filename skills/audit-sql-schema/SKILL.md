---
name: audit-sql-schema
description: Audit SQL table schemas to verify that CREATE TABLE statements include all columns added by migrations. Use when adding a database column, after a schema change, or to check for drift between CREATE TABLE and migration blocks.
---

Audit the SQL table schema files in this project for consistency between CREATE TABLE statements and migration blocks (ALTER TABLE ADD COLUMN).

## What to check

For each table file in `server/src/database/tables/` (and inline tables in `server/src/database/database.ts`):

1. Read the CREATE TABLE statement and list every column defined there.
2. Read every migration block (the `DO $$ BEGIN ... IF NOT EXISTS ... ALTER TABLE ADD COLUMN` pattern) and list every column added via migration.
3. Report any column that exists in a migration but is MISSING from the CREATE TABLE statement.

These must always be in sync: the CREATE TABLE is for fresh databases, the migration is for existing databases. A column in one but not the other means either new installs or existing installs will be missing the column.

## Output

Report a table of findings:

| Table | Column | Status |
|-------|--------|--------|
| ... | ... | OK / MISSING from CREATE TABLE |

If all columns are in sync, report that the audit passed.

If any are out of sync, show the exact fix needed (the line to add to the CREATE TABLE statement) and offer to apply it.
