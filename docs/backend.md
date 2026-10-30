# Backend

The FastAPI service between the frontend and the vendor. It validates input, holds the vendor `api-key`, calls the vendor with a timeout and retries, and maps every outcome to a safe response.

## Layers

- **API** (`app/api/`) — HTTP only: parses requests into Pydantic models (shape and types), calls the service, maps domain errors to error codes and statuses; no business decisions
- **Business** (`app/quotes/service.py`) — whether quotes can be served, business bounds, asks the vendor client for a quote; raises domain errors; knows nothing about HTTP
- **Vendor client** (`app/quotes/vendor.py`) — implements the `VendorClient` port: sends the key in the `api-key` header, never follows redirects (a redirect could send the key to another host), applies timeout and retry, checks replies against the contract with a Pydantic model, raises typed vendor errors
- **Config** (`app/config.py`) — loads settings and reports which are missing or invalid

The service depends on the `VendorClient` port, so tests inject a fake and the real vendor needs only a new URL and key.

```text
backend/
  app/
    main.py
    factory.py
    config.py
    log.py
    api/quotes.py
    quotes/models.py
    quotes/service.py
    quotes/vendor.py
  tests/
```

## Endpoints

`GET /api/v1/health` — liveness only: 200 `{ "status": "ok" }` whenever the process is up, even when quotes are unavailable.

`GET /api/v1/quotes/status` — 200 always:

- `available` — boolean
- `requestTimeoutSeconds` — how long the frontend waits for `POST /api/v1/quotes`, from `FRONTEND_REQUEST_TIMEOUT_SECONDS`; null when unavailable
- `limits` — `loanAmountMin`, `loanAmountMax`, `loanAmountMaxDecimals`, `loanTermMonthsMin`, `loanTermMonthsMax`, all JSON numbers; null when unavailable

`POST /api/v1/quotes` — request and 200 response use the vendor contract's field names. `loanAmount` and `totalCommission` are decimal strings on this API and JSON numbers to and from the vendor ([`vendor-api.md`](vendor-api.md)); `commissionRate` is a JSON number and `loanTermInMonths` a JSON integer. `totalCommission` is the vendor's value in plain non-negative decimal notation, with no exponent (`"15.00"`, `"1500"`). The backend never converts money through a float: JSON is decoded with `Decimal` first and then validated by a Pydantic model, and a small exact writer sends JSON numbers. The backend first checks it can serve quotes, then validates, then calls the vendor. The availability check runs before any body validation, so an unavailable backend returns `QUOTES_UNAVAILABLE` whatever the body.

## Request ID

- The backend assigns each request a UUID v4; any inbound `X-Request-ID` is ignored
- Every response from `/api/v1/*`, including errors, carries it in an `X-Request-ID` header; error bodies also carry it as `requestId`
- Every log line for the request carries it

## Missing or invalid config

- The backend always starts, even when config is missing or invalid
- Config is read once at startup; a config change takes effect on restart
- Config is invalid when a required setting is missing or blank, `VENDOR_API_KEY` contains characters not allowed in an HTTP header value (e.g. a newline or non-ASCII), `VENDOR_QUOTE_URL` is not an `http` or `https` URL with a valid host and port, or a set value is not a finite number, is not a whole number where one is expected (retries, decimal places, term limits), is negative, has a min above its max, `VENDOR_TIMEOUT_SECONDS` is 0 or less, `FRONTEND_REQUEST_TIMEOUT_SECONDS` is not above the worst case in § Latency, `LOAN_AMOUNT_MIN` is 0 or less, `LOAN_AMOUNT_MAX_DECIMALS` is 0 (amounts are entered in dollars and cents), or `LOAN_TERM_MONTHS_MIN` is below 1
- Invalid config makes the backend unavailable: status reports `available: false`, and each problem is logged at ERROR on startup
- A vendor 401 does not make the backend unavailable; each request reports it, and the next request tries the vendor again

## Validation

Shape and types (API layer):

- All three fields required; extra fields rejected
- `loanAmount` — a JSON string that fully matches `-?[0-9]+(\.[0-9]+)?`, ASCII digits only (`"1234.50"`, `"007"`); JSON numbers, booleans, exponents, `"+1"`, `"1."`, `"1_000"`, `" 1"` and `""` rejected
- `loanTermInMonths` — a JSON integer; strings, booleans, and numbers such as `12.5`, `12.0` and `1e2` rejected
- `riskBand` — exactly `LOW`, `MEDIUM` or `HIGH`

Business bounds (business layer), inclusive, from config:

- `loanAmount` between `LOAN_AMOUNT_MIN` and `LOAN_AMOUNT_MAX`, with at most `LOAN_AMOUNT_MAX_DECIMALS` decimal places, counted on that `Decimal` ignoring trailing zeros (`"1.100"` has 1)
- `loanTermInMonths` between `LOAN_TERM_MONTHS_MIN` and `LOAN_TERM_MONTHS_MAX`
- Zero and negative amounts and terms always fail the range check, since both minimums must be above 0
- A `loanAmount` string of any length that matches the format, if out of bounds, fails the range check
- A number in the body that the JSON decoder rejects as too large makes the body unparseable (status 400, below); any `loanTermInMonths` the decoder accepts, if out of bounds, fails the range check
- None of these ever returns `INTERNAL_ERROR`

Both return `VALIDATION_FAILED` with one entry per failing field.

- Each field gets only its first failing check; the combined order across both layers for `loanAmount` is: not a number, too many decimal places, out of range
- Shape errors are returned first; business bounds are checked only when the whole body's shape is valid, so a shape error on any field means no bound errors are returned
- `fields[].field` is the request field's name: `loanAmount`, `loanTermInMonths`, `riskBand`, or the name of an extra field
- `fields[].code` names the failed rule: `REQUIRED`, `NOT_A_NUMBER`, `TOO_MANY_DECIMALS`, `OUT_OF_RANGE`, `INVALID_VALUE` or `UNKNOWN_FIELD`
- A `loanAmount` that is not a JSON string, or is a string not in the format above, gets `NOT_A_NUMBER`; a `loanTermInMonths` of the wrong type or with decimals, or an unknown `riskBand`, gets `INVALID_VALUE`
- Field names may be echoed in `fields[].field`, but submitted values never are
- A body that is not valid JSON, not a JSON object (`[]`, `null`, a string), or sent without a JSON `Content-Type` (e.g. form-encoded; `application/json` with or without a `charset` parameter is accepted), returns `VALIDATION_FAILED` with status 400 and no `fields`

## Vendor retry

- Each attempt times out after `VENDOR_TIMEOUT_SECONDS`, a total deadline covering connect and the whole response; the HTTP client's per-phase timeouts alone do not meet this
- Retried up to `VENDOR_MAX_RETRIES` times: connection error, timeout, any 5xx
- Never retried: any 4xx (including 408 and 429), or a bad response
- Backoff before a retry: `VENDOR_RETRY_BACKOFF_MS`, plus random jitter of up to half that
- A 200 whose body breaks the contract is a bad response: `quoteId` missing, empty or not a string; `commissionRate` or `totalCommission` missing, negative, or not a JSON number — numeric strings such as `"0.015"`, booleans, `NaN` and `Infinity` all count as not a number
- A 4xx other than 401, any 3xx, a 2xx other than 200, or a 200 whose body cannot be decoded (e.g. a corrupt `Content-Encoding`) or is not JSON, is also a bad response
- When retries run out, the error code follows the last attempt
- A vendor 504 is a vendor reply, so it maps to `VENDOR_UNAVAILABLE`; `VENDOR_TIMEOUT` is only for our own timeout
- A slow vendor reply that arrives after our timeout is discarded

## Latency

- Worst case for `POST /api/v1/quotes`: `(VENDOR_MAX_RETRIES + 1) × VENDOR_TIMEOUT_SECONDS` plus `VENDOR_MAX_RETRIES × 1.5 × VENDOR_RETRY_BACKOFF_MS` — about 6.4 s with the defaults
- The backend always answers within that worst case, with a quote or an error
- nginx's proxy timeout (default 60 s) must stay above the worst case, so a slow vendor always reaches the user as `VENDOR_TIMEOUT`, never as an nginx error

## Error responses

Every error has one shape; `fields` appears only for `VALIDATION_FAILED`.

```json
{ "error": { "code": "…", "requestId": "…", "fields": [ { "field": "…", "code": "…" } ] } }
```

- `VALIDATION_FAILED` (422) — input fails shape or business-bound checks; 400 when the body cannot be parsed as a JSON object
- `QUOTES_UNAVAILABLE` (503) — the backend is unavailable
- `VENDOR_AUTH_FAILED` (502) — vendor returned 401
- `VENDOR_UNAVAILABLE` (502) — vendor returned any 5xx, or a connection error, after retries
- `VENDOR_TIMEOUT` (504) — vendor timed out after retries
- `VENDOR_BAD_RESPONSE` (502) — any other unexpected vendor reply (see Vendor retry)
- `INTERNAL_ERROR` (500) — anything unexpected; no internal detail in the body

The backend sends codes only, never user-facing text; the frontend maps every code to its own wording. Vendor error bodies are never passed through.

## Logging

JSON lines to stdout; every line carries the request ID. Never logged: the key (see [`overview.md`](overview.md) § Security) or any request headers.

- Startup — each missing or invalid setting at ERROR
- Each quote request — outcome code, total latency, and the loan inputs only when the body's shape is valid, at INFO
- Each vendor attempt — attempt number, status or failure, latency, and `quoteId` on success
- Vendor 401 — at ERROR, as an auth failure

## Config

Loaded as described in [`running.md`](running.md) § Config files.

Required:

- `VENDOR_QUOTE_URL` — full URL of the vendor's quote endpoint
- `VENDOR_API_KEY` — our copy of the vendor key

With code defaults:

- `VENDOR_TIMEOUT_SECONDS` — per-attempt timeout; default `3`
- `VENDOR_MAX_RETRIES` — retries after the first attempt; default `1`
- `VENDOR_RETRY_BACKOFF_MS` — base delay before a retry; default `250`
- `FRONTEND_REQUEST_TIMEOUT_SECONDS` — sent to the frontend in status; default `15`
- `LOAN_AMOUNT_MIN`, `LOAN_AMOUNT_MAX`, `LOAN_AMOUNT_MAX_DECIMALS` — limits on the user-entered loan amount (smallest, largest, decimal places allowed); defaults `1`, `10000000`, `2`
- `LOAN_TERM_MONTHS_MIN`, `LOAN_TERM_MONTHS_MAX` — limits on the user-entered term (shortest, longest, in months); defaults `1`, `360`

## Tests

Vendor faked with an httpx mock transport.

- Validation — a table of invalid inputs, each returning `VALIDATION_FAILED` with field errors; it includes a body that is not JSON and a body that is `[]`
- Number formats — a JSON number `loanAmount` returns `NOT_A_NUMBER`; the vendor receives `loanAmount` as a JSON number; our response has `totalCommission` as a string
- Missing config — a missing key reports `available: false`, and `POST` returns `QUOTES_UNAVAILABLE`
- Retry — 5xx then success returns the quote; persistent 5xx returns `VENDOR_UNAVAILABLE`; a persistent vendor 504 returns `VENDOR_UNAVAILABLE`; persistent timeout returns `VENDOR_TIMEOUT`; 401 is not retried and returns `VENDOR_AUTH_FAILED`
- Bad response — a 200 that breaks the contract returns `VENDOR_BAD_RESPONSE`; the cases include `NaN` for `totalCommission`
- Unexpected error — an unhandled exception returns `INTERNAL_ERROR` with no internal detail
