# Vendor API

The vendor mock: a FastAPI app that simulates the third-party Commission Quote API to the agreed contract, including its key check and random failures. The request and response fields are fixed by the brief and cannot change.

## Endpoint

`POST /commission-quotes` — the brief names no path; this one is our choice.

Request — a JSON object with a JSON `Content-Type`; all three fields required and extra fields rejected. The mock is a third party, so these are its own rules, independent of our backend's:

- `loanAmount` — a JSON number greater than 0; strings, booleans, `NaN` and `Infinity` rejected; read as a `Decimal` from the number as sent, never via a float
- `loanTermInMonths` — a JSON integer greater than 0; strings, booleans and decimals rejected
- `riskBand` — exactly `LOW`, `MEDIUM` or `HIGH`

Response (200):

- `quoteId` — UUID v4 string
- `commissionRate` — decimal fraction, e.g. `0.015` for 1.5%
- `totalCommission` — rounded as in Pricing; trailing zeros are not significant (`12.5` means `12.50`)

`commissionRate` and `totalCommission` are serialised as JSON numbers, never strings.

## Order of checks

1. `api-key` header — runs before any body validation, so a missing or wrong key returns 401 `{ "error": "Unauthorized" }` whatever the body; the same body for both; compared in constant time; a malformed header (non-ASCII, or sent more than once) is a wrong key and also returns 401, never a 500
2. Request body — invalid, not JSON, not a JSON object, or holding a number too large to price returns 422 `{ "error": "…" }`, never a 500
3. Simulated fault — may fire, see below
4. Quote — calculated and returned

Auth and validation never fail at random.

## Pricing

- `commissionRate` — the configured rate for the request's risk band
- `totalCommission` — `loanAmount × commissionRate`, using `Decimal`, rounded half-up to cents
- `loanTermInMonths` is validated but does not affect the price

## Simulated faults

- With probability `FAILURE_RATE`, return 500, 502 or 503, chosen at random
- Otherwise, with probability `SLOW_RESPONSE_RATE`, wait `SLOW_RESPONSE_DELAY_SECONDS` before returning the quote
- A rate of 0 never fires and 1 always fires, so tests are deterministic

## Logging

JSON lines to stdout, one per request: outcome (auth rejected, invalid, fault injected, quote issued) and latency. The key is never logged (see [`overview.md`](overview.md) § Security).

## Config

Loaded as described in [`running.md`](running.md) § Config files. The mock is not user-facing, so it refuses to start if config is missing or invalid: a blank key, a value that is not a finite number, a commission rate or probability outside 0–1, or a negative delay.

Required:

- `VENDOR_API_KEY` — the one valid key

With code defaults:

- `COMMISSION_RATE_LOW`, `COMMISSION_RATE_MEDIUM`, `COMMISSION_RATE_HIGH` — rate per risk band, as a decimal fraction; defaults `0.01`, `0.015`, `0.0225`
- `FAILURE_RATE` — probability of a 5xx response, 0–1; default `0.2`
- `SLOW_RESPONSE_RATE` — probability of a slow response, 0–1; default `0.1`
- `SLOW_RESPONSE_DELAY_SECONDS` — delay for a slow response; must exceed the backend's `VENDOR_TIMEOUT_SECONDS` (an operator rule; neither app checks it); default `5`

## Layout

Same shape as the backend: `vendor-mock/app/` for the code and `vendor-mock/tests/` for the tests.

## Tests

- Key check: missing or wrong key returns 401; the right key returns 200
- Order of checks: a wrong key with an invalid body returns 401, not 422
- Validation: an invalid body with the right key returns 422
- Pricing: rate per band and half-up rounding to cents
- Number format: the raw response body has `commissionRate` and `totalCommission` as JSON numbers, not strings
- Faults: with `FAILURE_RATE=1`, every request returns a 5xx
