# Frontend

The staff-facing React page: a loan form, a Generate Quote button, the resulting quote, and clear loading, unavailable and error states. It talks only to the backend, and owns all text the user sees; the backend sends only codes.

## Structure

```text
frontend/src/
  api/          typed client for /api/v1/quotes/status and /api/v1/quotes
  components/   QuoteForm, QuoteResult, StatusBanner
  App.tsx
```

## On load

- Calls `GET /api/v1/quotes/status` and shows a brief loading state
- `available: false` — the form shows greyed out with a banner showing the `QUOTES_UNAVAILABLE` message (see Errors)
- Status call fails — treated as unavailable, with "Can't reach the quote service."
- `available: true` but `limits` or `requestTimeoutSeconds` missing or malformed — treated as `available: false`
- Unavailable is not retried automatically; the user reloads the page to try again

## Form

- Loan amount — text input with `inputmode="decimal"`; only `0`–`9` and `.` are allowed
- Term in months — text input with `inputmode="numeric"`; only `0`–`9` are allowed
- The field's value is filtered on every change, whatever the input method (typing, an on-screen keyboard, autofill, drag-and-drop), not by intercepting key presses; a typed disallowed character simply does not appear
- A paste containing any character a field does not allow is rejected whole, leaving the field unchanged, so a pasted value is never silently altered (e.g. `1,5` never becomes `15`)
- Risk band — select: Low, Medium, High (sent as `LOW`, `MEDIUM`, `HIGH`), starting on an empty placeholder option
- Every field has a label, and its error is linked to it for screen readers
- The layout is responsive and usable at phone width
- All fields start empty; there are no prefilled values

## Validation

- Checked on leaving a field and on submit, against the `limits` from status
- Generate Quote stays enabled; submitting invalid values shows the field errors and sends nothing
- A valid amount is digits, optionally followed by `.` and at least one more digit: `007` and `1.5` pass; `.5`, `1.` and `1.2.3` are not a number
- Decimal places are counted on the text as typed, so `1.100` has 3; this is slightly stricter than the backend, which is fine
- Each field shows only its first failing check: empty first, then the order in [`backend.md`](backend.md) § Validation
- The amount is sent as the validated text unchanged (`007` is sent as `"007"`), and the term as an integer built from the validated text (`007` is sent as `7`); types are in [`backend.md`](backend.md) § Endpoints

Field error messages, used both for the frontend's own checks and for the matching server `fields[].code`, with `$min` and `$max` formatted as money (e.g. `$1.00`, `$10,000,000.00`) and term limits and `N` as plain whole numbers (e.g. "between 1 and 360 months"):

- Empty (`REQUIRED`) — "Enter a loan amount." / "Enter a loan term." / "Select a risk band."
- Loan amount not a number (`NOT_A_NUMBER`) — "Loan amount must be a number."
- Loan amount out of range (`OUT_OF_RANGE`) — "Loan amount must be between $min and $max."
- Loan amount has too many decimal places (`TOO_MANY_DECIMALS`) — "Loan amount can have at most N decimal places."
- Term out of range (`OUT_OF_RANGE`) — "Term must be between min and max months."
- Any other invalid value (`INVALID_VALUE`) — "Select a risk band." for the risk band; "Enter a valid value." otherwise

## Generating

- Submitting clears any previous result and error banner as the request starts
- While waiting, the button reads "Generating…", the button and inputs are disabled, and the form is marked busy
- Changing any input after a quote or error is shown clears the result and the error banner
- `POST /api/v1/quotes` times out after `requestTimeoutSeconds` from status; a timed-out request is aborted, so a late response is never shown, and the timeout shows the `VENDOR_TIMEOUT` message
- The status call itself has no timeout; if it stalls, the page stays on its loading state

## Result

- Quote ID
- Commission rate as a percentage with 2 decimal places, e.g. `1.50%`
- Total commission as `$` with comma separators and 2 decimal places, e.g. `$1,234.56`; the vendor has already rounded it, so the frontend only formats and never rounds again
- Total commission is converted to a number only to format it for display
- A valid quote has a non-empty `quoteId`, a finite number for `commissionRate`, and a `totalCommission` string fully matching `[0-9]+(\.[0-9]+)?` that converts to a finite number; anything else is treated as in Errors

## Errors

An alert banner shows a message chosen by error `code`, then "Reference: <requestId>". The reference line is left out when there is no `requestId` (a network failure, or an error without a JSON body). The form keeps its values.

- Server field errors from `VALIDATION_FAILED` show the field error message for their `fields[].code` beside the input; editing that field or submitting again clears them
- Server field errors for names other than the three inputs, or with an unknown code, are dropped; a `VALIDATION_FAILED` with no usable fields shows "Something went wrong. Please try again." instead, since nothing is highlighted

Messages by code:

- `VALIDATION_FAILED` — "Please fix the highlighted fields."
- `QUOTES_UNAVAILABLE` — "Commission quotes aren't currently available."
- `VENDOR_AUTH_FAILED` — "The quote service rejected our credentials. Please contact support."
- `VENDOR_UNAVAILABLE` — "The quote service is having problems. Please try again."
- `VENDOR_TIMEOUT` — "The quote service took too long to respond. Please try again."
- `VENDOR_BAD_RESPONSE` — "The quote service returned an unexpected response. Please try again."
- `INTERNAL_ERROR`, an unknown code, no response, or a success response that is not a valid quote — "Something went wrong. Please try again."

## Tests

`fetch` mocked.

- Unavailable — the form is greyed out with the banner
- Invalid input — submitting shows the field errors and sends no request
- Success — submitting shows the formatted result
- Errors — for each error code, submitting shows that code's message and the reference
