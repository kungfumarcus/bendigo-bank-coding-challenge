# Decisions

Impactful decisions for the Commission Quote App — one line each.

- **D1** — Use spec-first development to build the app. Focus on fully scoped and correct specifications before any coding.
- **D2** — Use Python/FastAPI and React as the stack.
- **D3** — Our backend sits between the UI and the vendor and holds the vendor `api-key`; the browser never talks to the vendor.
- **D4** — Treat the vendor mock as a real external third party: its own network and config, reached only by URL and key.
- **D5** — Missing or invalid config disables only the function that depends on it (e.g. the quote calculator), never the whole backend; that function reports itself unavailable and its part of the page greys out.
- **D6** — The backend is the single source of every tunable value; the frontend gets its validation limits and request timeout from the backend rather than hard-coding them.
- **D7** — The backend reports errors as fixed codes, and the frontend owns the text users see.
- **D8** — Requests and vendor replies are validated by Pydantic models, so adding a field is a small change; JSON is decoded with `Decimal` first, and a small exact writer sends JSON numbers, because Pydantic alone would read numbers through a float and write `Decimal` as a string.
- **D9** — A quote's `loanAmount` and `totalCommission` are decimal strings on our own API, so the backend never uses a float for money and the browser uses a number only for display; the vendor contract keeps JSON numbers, and the status `limits` stay numbers.
