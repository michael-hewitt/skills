# Superhuman Docs / Coda API reference notes

Base URL: `https://coda.io/apis/v1` (the same API also answers at
`https://docs.superhuman.com/apis/v1`). Auth: `Authorization: Bearer <token>`.
Full docs: https://coda.io/developers/apis/v1

## Ids found in links

| In the link | Meaning | API id |
|---|---|---|
| `/d/Timesheet-Reloaded_dSgv9itPXHL` | doc | `Sgv9itPXHL` |
| `/Timesheet_suJ71F23` | page | `canvas-haOqJ71F23` (browserLink ends in `_suJ71F23`) |
| `#_lu4mexAN` | section anchor within the page | not addressable via the API |

The page suffix is not the API page id. The script resolves it by listing
`GET /docs/{docId}/pages` and matching the `browserLink` suffix; a page name also works.

Tables: `grid-...` is a base table, `table-...` is a view; both accept the same
`/tables/{id}/rows` calls. Table names work in the URL when unique (URL-encoded).

## Endpoints the script uses

| Call | Notes |
|---|---|
| `GET /whoami` | validates a token; returns `loginId` |
| `GET /docs/{docId}` | 404 when the account cannot see the doc (not 403) |
| `GET /docs/{docId}/pages` | paginated via `nextPageToken` |
| `POST /docs/{docId}/pages/{pageId}/export` `{"outputFormat":"markdown"|"html"}` | async; poll `GET .../export/{requestId}` until `status: complete`, then fetch `downloadLink` (S3, gzip-compressed body; only GET works, HEAD is 403) |
| `GET /docs/{docId}/tables` | `tableType` is `table` or `view`; `parent.name` is the page |
| `GET /docs/{docId}/tables/{id}/columns` | `format.type`: text, number, date, time, dateTime, person, select, lookup, ... |
| `GET /docs/{docId}/tables/{id}/rows?useColumnNames=true&valueFormat=simple&limit=200` | paginated via `nextPageToken`; `query=Column:"value"` filters server-side |

## Quirks

- **Page export omits table rows.** A markdown export renders each table as a header row
  only. Read the table through `/rows`.
- **Time columns** come back as `1899-12-30T11:35:00.000-08:00`: only the time part means
  anything. `dateTime` columns carry the real date.
- **Rate limits** are per token; the script honours `Retry-After` on 429 and retries up to
  five times.
- **Row values** in `simple` format are strings/numbers; use `--json` (raw items) if a
  richer format is needed, or `get ... --param valueFormat=rich`.
- Writes (`POST /rows`, `PUT /rows/{id}`, `DELETE`) exist in the API and are reachable
  through `request`, but the skill treats docs as read-only unless the user asks.

## Known docs

| Doc | Account | Id |
|---|---|---|
| Timesheet Reloaded (Financial folder, crescendosw.com workspace) | michael@crescendosw.com | `Sgv9itPXHL` |
