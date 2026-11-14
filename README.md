# shorturl

A URL shortener with a real HTTP API, SQLite storage and no dependencies. Short codes
are base62 of the row id, so they are stable, collision-free by construction, and grow
in width only when the id space demands it.

## Install

Python 3.11+, nothing to install.

```
git clone https://github.com/CodingWithFardin/shorturl.git
cd shorturl
python -m unittest discover -s tests -t .
python -m shorturl.server --db links.db --port 8080
```

## API

Create a link:

```
curl -s -X POST localhost:8080/api/links \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://example.com/a/very/long/path"}'
{"code":"000001","short":"http://localhost:8080/000001"}
```

Follow it:

```
curl -si localhost:8080/000001 | head -1
HTTP/1.1 302 Found
```

Read stats:

```
curl -s localhost:8080/api/links/000001
{"code":"000001","url":"https://example.com/a/very/long/path","hits":3,...}
```

`GET /health` returns `ok` and touches nothing. `GET /api/links` lists the busiest links.

## Behaviour worth knowing

- Shortening the same URL twice returns the same code; there is no duplicate row.
- Only absolute URLs (`scheme://host/...`) are accepted; anything else is a 400.
- Codes are validated by alphabet and length before the database is touched, so
  junk paths never reach a query.
- Hit counts update in the same statement that resolves the link.

## Files

- `shorturl/store.py` - schema, code encoding, shorten/resolve/stats.
- `shorturl/server.py` - request routing and JSON handlers.
- `tests/` - routing, idempotency, hit counting and error paths.

MIT, 2026.
