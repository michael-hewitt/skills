#!/usr/bin/env python3
"""Read Superhuman Docs (formerly Coda) documents through the Coda REST API.

Tries the michael@crescendosw.com account first and falls back to michael@hewitts.us
when the first account cannot see the doc. Tokens come from environment variables
CODA_TOKEN_CRESCENDOSW / CODA_TOKEN_HEWITTS, or from the .env file at the root of the
skills repository (two directories above this skill). Standard library only.

Usage: coda.py <command> [args] [--account crescendosw|hewitts] [--json]

  whoami                               show which accounts have working tokens
  doc     <doc>                        doc metadata (name, owner, workspace, folder)
  pages   <doc>                        list pages with ids and browser links
  page    <doc> [page] [--html] [--out FILE]
                                       export a page's canvas as markdown (tables render empty;
                                       use `rows` for table contents). Page defaults to the one
                                       in the URL.
  tables  <doc>                        list tables and views
  columns <doc> <table>                list a table's columns and types
  rows    <doc> <table> [--limit N] [--all] [--query 'Column:"value"'] [--csv]
                                       rows with column names; markdown table by default
  get     <doc> <subpath> [--param k=v ...]
                                       raw GET of /docs/{id}/<subpath>, printed as JSON
  request <method> <path> [--data JSON]
                                       raw call against /apis/v1<path> with the chosen account

<doc> is a docs.superhuman.com or coda.io URL, or a bare doc id such as Sgv9itPXHL.
<page> is a browser suffix (suJ71F23), a canvas id (canvas-haOqJ71F23) or a page name.
<table> is a table id (grid-...), a view id (table-...) or a table name.

Exit codes: 0 ok, 1 API/usage error, 2 doc not visible to any account,
3 a token is missing (ask the user for it and add it to the .env file).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://coda.io/apis/v1'
ACCOUNTS = [
    ('crescendosw', 'michael@crescendosw.com', 'CODA_TOKEN_CRESCENDOSW'),
    ('hewitts', 'michael@hewitts.us', 'CODA_TOKEN_HEWITTS'),
]
ENV_FILE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.env'))


# ---------------------------------------------------------------- tokens

def load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(ENV_FILE):
        return values
    with open(ENV_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            value = value.split('#', 1)[0].strip().strip('"').strip("'")
            values[key.strip()] = value
    return values


def token_for(var: str) -> str | None:
    return os.environ.get(var) or load_env_file().get(var) or None


def missing_token_message(name: str, email: str, var: str) -> str:
    return (
        f'No API token for the {email} account ({name}).\n'
        f'Ask the user for that account\'s Superhuman Docs / Coda API token and add it to\n'
        f'{ENV_FILE} as {var}=<token> (or export {var}). Tokens are created at\n'
        f'https://coda.io/account under "API settings".'
    )


# ---------------------------------------------------------------- HTTP

class ApiError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f'HTTP {status}: {body[:500]}')
        self.status = status
        self.body = body


def call(token: str, method: str, path: str, params: dict | None = None, data: dict | None = None,
         raw: bool = False):
    url = path if path.startswith('http') else API + path
    if params:
        url += ('&' if '?' in url else '?') + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    body = json.dumps(data).encode() if data is not None else None
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Accept-Encoding', 'gzip')
        if body is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip' or content[:2] == b'\x1f\x8b':
                    content = gzip.decompress(content)
                if raw:
                    return content
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as e:
            text = e.read().decode('utf-8', 'replace')
            if e.code == 429 and attempt < 4:
                time.sleep(float(e.headers.get('Retry-After') or 2 * (attempt + 1)))
                continue
            raise ApiError(e.code, text) from None
    raise ApiError(429, 'rate limited after retries')


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as resp:
        content = resp.read()
    return gzip.decompress(content) if content[:2] == b'\x1f\x8b' else content


# ---------------------------------------------------------------- account resolution

def accounts_to_try(only: str | None):
    chosen = [a for a in ACCOUNTS if only is None or a[0] == only]
    if not chosen:
        die(f'unknown account {only!r}; use one of {[a[0] for a in ACCOUNTS]}')
    return chosen


def resolve_account(doc_id: str, only: str | None):
    """Return (name, email, token, doc_json) for the first account that can open the doc."""
    failures = []
    for name, email, var in accounts_to_try(only):
        token = token_for(var)
        if not token:
            if only:
                print(missing_token_message(name, email, var), file=sys.stderr)
                sys.exit(3)
            failures.append(f'{email}: token missing ({var})')
            continue
        try:
            doc = call(token, 'GET', f'/docs/{doc_id}')
            print(f'[coda] {doc.get("name")!r} opened as {email}', file=sys.stderr)
            return name, email, token, doc
        except ApiError as e:
            if e.status in (401, 403, 404):
                failures.append(f'{email}: HTTP {e.status}')
                continue
            raise
    print(f'Doc {doc_id} is not visible to any account:\n  ' + '\n  '.join(failures), file=sys.stderr)
    if any('token missing' in f for f in failures):
        print('A token is missing: ask the user for it and add it to ' + ENV_FILE, file=sys.stderr)
        sys.exit(3)
    sys.exit(2)


# ---------------------------------------------------------------- parsing

def parse_doc_ref(ref: str) -> tuple[str, str | None]:
    """Return (docId, pageSuffix|None) from a URL or bare id."""
    m = re.search(r'_d([A-Za-z0-9_-]+)', ref)
    doc_id = m.group(1) if m else ref.strip().lstrip('d') if ref.startswith('d') and len(ref) > 10 else ref.strip()
    if not m and '/' in ref:
        die(f'could not find a doc id (…_dXXXXXXXXXX) in {ref!r}')
    pm = re.search(r'_su([A-Za-z0-9_-]+)', ref)
    return doc_id, (pm.group(1) if pm else None)


def list_all(token: str, path: str, params: dict | None = None, limit: int | None = None):
    items, params = [], dict(params or {})
    while True:
        page = call(token, 'GET', path, params)
        items.extend(page.get('items', []))
        if limit is not None and len(items) >= limit:
            return items[:limit]
        if not page.get('nextPageToken'):
            return items
        params['pageToken'] = page['nextPageToken']


def find_page(token: str, doc_id: str, ref: str) -> dict:
    pages = list_all(token, f'/docs/{doc_id}/pages')
    for p in pages:
        if p['id'] == ref or p.get('browserLink', '').endswith('_su' + ref) or ref.startswith('su') and p.get('browserLink', '').endswith('_' + ref):
            return p
    for p in pages:
        if p.get('name', '').lower() == ref.lower():
            return p
    die(f'no page {ref!r} in doc {doc_id}; pages: ' + ', '.join(f'{p["name"]} ({p["id"]})' for p in pages))


def find_table(token: str, doc_id: str, ref: str) -> dict:
    try:
        return call(token, 'GET', f'/docs/{doc_id}/tables/{urllib.parse.quote(ref, safe="")}')
    except ApiError as e:
        if e.status != 404:
            raise
    tables = list_all(token, f'/docs/{doc_id}/tables')
    die(f'no table {ref!r} in doc {doc_id}; tables: ' + ', '.join(f'{t["name"]} ({t["id"]})' for t in tables))


# ---------------------------------------------------------------- output

def die(msg: str, code: int = 1):
    print('error: ' + msg, file=sys.stderr)
    sys.exit(code)


def out_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cell(v) -> str:
    if v is None:
        return ''
    if isinstance(v, (list, dict)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v).replace('|', '\\|').replace('\n', ' ')


def print_markdown_table(headers: list[str], rows: list[list]):
    print('| ' + ' | '.join(headers) + ' |')
    print('| ' + ' | '.join('---' for _ in headers) + ' |')
    for r in rows:
        print('| ' + ' | '.join(cell(v) for v in r) + ' |')


# ---------------------------------------------------------------- commands

def cmd_whoami(args):
    for name, email, var in accounts_to_try(args.account):
        token = token_for(var)
        if not token:
            print(f'{name:12} {email:28} NO TOKEN ({var} missing)')
            continue
        try:
            me = call(token, 'GET', '/whoami')
            print(f'{name:12} {email:28} ok (login {me.get("loginId")}, token {me.get("tokenName")!r})')
        except ApiError as e:
            print(f'{name:12} {email:28} FAILED HTTP {e.status}')


def cmd_doc(args):
    doc_id, _ = parse_doc_ref(args.doc)
    name, email, token, doc = resolve_account(doc_id, args.account)
    if args.json:
        return out_json(doc)
    print(f'{doc["name"]}  (id {doc["id"]})')
    print(f'  account:   {email}')
    print(f'  owner:     {doc.get("owner")}')
    print(f'  workspace: {doc.get("workspace", {}).get("name")}')
    print(f'  folder:    {doc.get("folder", {}).get("name")}')
    print(f'  link:      {doc.get("browserLink")}')
    print(f'  updated:   {doc.get("updatedAt")}')


def cmd_pages(args):
    doc_id, _ = parse_doc_ref(args.doc)
    _, _, token, _ = resolve_account(doc_id, args.account)
    pages = list_all(token, f'/docs/{doc_id}/pages')
    if args.json:
        return out_json(pages)
    print_markdown_table(['id', 'name', 'parent', 'browserLink'],
                         [[p['id'], p['name'], (p.get('parent') or {}).get('name', ''), p.get('browserLink', '')] for p in pages])


def cmd_page(args):
    doc_id, suffix = parse_doc_ref(args.doc)
    ref = args.page or suffix
    if not ref:
        die('no page given and the URL has no page suffix (…_suXXXX); run `pages` to list them')
    _, _, token, _ = resolve_account(doc_id, args.account)
    page = find_page(token, doc_id, ref)
    fmt = 'html' if args.html else 'markdown'
    job = call(token, 'POST', f'/docs/{doc_id}/pages/{page["id"]}/export', data={'outputFormat': fmt})
    status_path = f'/docs/{doc_id}/pages/{page["id"]}/export/{job["id"]}'
    for _ in range(60):
        status = call(token, 'GET', status_path)
        if status.get('status') == 'complete':
            break
        if status.get('status') == 'failed':
            die('export failed: ' + json.dumps(status))
        time.sleep(1.5)
    else:
        die('export did not complete within 90 s')
    content = download(status['downloadLink']).decode('utf-8', 'replace')
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'wrote {len(content)} chars of {fmt} for page {page["name"]!r} to {args.out}')
    else:
        print(content)


def cmd_tables(args):
    doc_id, _ = parse_doc_ref(args.doc)
    _, _, token, _ = resolve_account(doc_id, args.account)
    tables = list_all(token, f'/docs/{doc_id}/tables')
    if args.json:
        return out_json(tables)
    print_markdown_table(['id', 'name', 'type', 'page'],
                         [[t['id'], t['name'], t.get('tableType', ''), (t.get('parent') or {}).get('name', '')] for t in tables])


def cmd_columns(args):
    doc_id, _ = parse_doc_ref(args.doc)
    _, _, token, _ = resolve_account(doc_id, args.account)
    table = find_table(token, doc_id, args.table)
    cols = list_all(token, f'/docs/{doc_id}/tables/{table["id"]}/columns')
    if args.json:
        return out_json(cols)
    print(f'{table["name"]} ({table["id"]}), {table.get("rowCount", "?")} rows')
    print_markdown_table(['id', 'name', 'type', 'display'],
                         [[c['id'], c['name'], (c.get('format') or {}).get('type', ''), 'yes' if c.get('display') else ''] for c in cols])


def cmd_rows(args):
    doc_id, _ = parse_doc_ref(args.doc)
    _, _, token, _ = resolve_account(doc_id, args.account)
    table = find_table(token, doc_id, args.table)
    params = {'useColumnNames': 'true', 'valueFormat': 'simple', 'limit': 200, 'query': args.query}
    limit = None if args.all else args.limit
    rows = list_all(token, f'/docs/{doc_id}/tables/{table["id"]}/rows', params, limit)
    if args.json:
        return out_json(rows)
    cols = [c['name'] for c in list_all(token, f'/docs/{doc_id}/tables/{table["id"]}/columns')]
    headers = ['rowId'] + cols
    data = [[r['id']] + [r['values'].get(c) for c in cols] for r in rows]
    if args.csv:
        w = csv.writer(sys.stdout)
        w.writerow(headers)
        w.writerows(data)
        return
    print(f'{table["name"]}: showing {len(rows)} of {table.get("rowCount", "?")} rows'
          + ('' if args.all or len(rows) < (args.limit or 0) else f' (use --all or --limit to see more)'))
    print_markdown_table(headers, data)


def cmd_get(args):
    doc_id, _ = parse_doc_ref(args.doc)
    _, _, token, _ = resolve_account(doc_id, args.account)
    params = dict(p.split('=', 1) for p in args.param)
    out_json(call(token, 'GET', f'/docs/{doc_id}/{args.subpath.lstrip("/")}', params))


def cmd_request(args):
    name, email, var = accounts_to_try(args.account or 'crescendosw')[0]
    token = token_for(var)
    if not token:
        print(missing_token_message(name, email, var), file=sys.stderr)
        sys.exit(3)
    data = json.loads(args.data) if args.data else None
    out_json(call(token, args.method.upper(), args.path, data=data))


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--account', choices=[a[0] for a in ACCOUNTS], help='use only this account (default: try crescendosw, then hewitts)')
    ap.add_argument('--json', action='store_true', help='print raw JSON instead of a table')
    sub = ap.add_subparsers(dest='command', required=True)

    sub.add_parser('whoami').set_defaults(fn=cmd_whoami)
    p = sub.add_parser('doc'); p.add_argument('doc'); p.set_defaults(fn=cmd_doc)
    p = sub.add_parser('pages'); p.add_argument('doc'); p.set_defaults(fn=cmd_pages)
    p = sub.add_parser('page'); p.add_argument('doc'); p.add_argument('page', nargs='?')
    p.add_argument('--html', action='store_true'); p.add_argument('--out'); p.set_defaults(fn=cmd_page)
    p = sub.add_parser('tables'); p.add_argument('doc'); p.set_defaults(fn=cmd_tables)
    p = sub.add_parser('columns'); p.add_argument('doc'); p.add_argument('table'); p.set_defaults(fn=cmd_columns)
    p = sub.add_parser('rows'); p.add_argument('doc'); p.add_argument('table')
    p.add_argument('--limit', type=int, default=50); p.add_argument('--all', action='store_true')
    p.add_argument('--query', help='Coda row filter, e.g. \'Category:"Renewal Support"\'')
    p.add_argument('--csv', action='store_true'); p.set_defaults(fn=cmd_rows)
    p = sub.add_parser('get'); p.add_argument('doc'); p.add_argument('subpath')
    p.add_argument('--param', action='append', default=[], metavar='k=v'); p.set_defaults(fn=cmd_get)
    p = sub.add_parser('request'); p.add_argument('method'); p.add_argument('path'); p.add_argument('--data'); p.set_defaults(fn=cmd_request)

    args = ap.parse_args(argv)
    try:
        args.fn(args)
    except ApiError as e:
        die(str(e))
    except (urllib.error.URLError, TimeoutError) as e:
        die(f'network error: {e}')


if __name__ == '__main__':
    main()
