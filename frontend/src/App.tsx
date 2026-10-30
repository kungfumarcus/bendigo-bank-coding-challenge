import { useEffect, useState } from "react";
import {
  ApiError,
  createQuote,
  fetchQuoteStatus,
  type Limits,
  type Quote,
  type QuoteRequest,
} from "./api/client";
import { QuoteForm, usableFieldErrors } from "./components/QuoteForm";
import { QuoteResult } from "./components/QuoteResult";
import { StatusBanner } from "./components/StatusBanner";
import {
  errorMessage,
  GENERIC_MESSAGE,
  UNREACHABLE_MESSAGE,
  type FieldName,
} from "./messages";

type PageState =
  | { kind: "loading" }
  | { kind: "unavailable"; message: string }
  | { kind: "ready"; limits: Limits; requestTimeoutSeconds: number };

interface Banner {
  message: string;
  requestId?: string;
}

export function App() {
  const [page, setPage] = useState<PageState>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [quote, setQuote] = useState<Quote>();
  const [banner, setBanner] = useState<Banner>();
  const [serverErrors, setServerErrors] = useState<
    Partial<Record<FieldName, string>>
  >({});

  useEffect(() => {
    fetchQuoteStatus()
      .then((status) =>
        setPage(
          status.available
            ? { kind: "ready", ...status }
            : {
                kind: "unavailable",
                message: errorMessage("QUOTES_UNAVAILABLE"),
              },
        ),
      )
      .catch(() =>
        setPage({ kind: "unavailable", message: UNREACHABLE_MESSAGE }),
      );
  }, []);

  if (page.kind === "loading") {
    return (
      <main>
        <h1>Commission Quote</h1>
        <p role="status">Loading…</p>
      </main>
    );
  }

  const limits = page.kind === "ready" ? page.limits : undefined;

  function showError(error: unknown) {
    const { code, requestId, fields } =
      error instanceof ApiError ? error : new ApiError();
    const usable = usableFieldErrors(fields, limits);
    setServerErrors(usable);
    const nothingHighlighted =
      code === "VALIDATION_FAILED" && Object.keys(usable).length === 0;
    setBanner({
      message: nothingHighlighted ? GENERIC_MESSAGE : errorMessage(code),
      requestId,
    });
  }

  async function submit(request: QuoteRequest) {
    if (page.kind !== "ready") {
      return;
    }
    setQuote(undefined);
    setBanner(undefined);
    setServerErrors({});
    setBusy(true);
    try {
      setQuote(await createQuote(request, page.requestTimeoutSeconds));
    } catch (error) {
      showError(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Commission Quote</h1>
      {page.kind === "unavailable" && <StatusBanner message={page.message} />}
      <QuoteForm
        limits={limits}
        busy={busy}
        serverErrors={serverErrors}
        onChange={() => {
          setQuote(undefined);
          setBanner(undefined);
        }}
        onClearServerError={(field) =>
          setServerErrors((current) => ({ ...current, [field]: undefined }))
        }
        onSubmit={submit}
      />
      {banner && (
        <StatusBanner message={banner.message} requestId={banner.requestId} />
      )}
      {quote && <QuoteResult quote={quote} />}
    </main>
  );
}
