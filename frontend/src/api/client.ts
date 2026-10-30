export type RiskBand = "LOW" | "MEDIUM" | "HIGH";

export interface Limits {
  loanAmountMin: number;
  loanAmountMax: number;
  loanAmountMaxDecimals: number;
  loanTermMonthsMin: number;
  loanTermMonthsMax: number;
}

export type QuoteStatus =
  | { available: false }
  | { available: true; limits: Limits; requestTimeoutSeconds: number };

export interface QuoteRequest {
  loanAmount: string;
  loanTermInMonths: number;
  riskBand: RiskBand;
}

export interface Quote {
  quoteId: string;
  commissionRate: number;
  totalCommission: string;
}

export interface ApiFieldError {
  field: string;
  code: string;
}

/** A failed quote request; `code` and `requestId` are absent when no error body came back. */
export class ApiError extends Error {
  constructor(
    readonly code?: string,
    readonly requestId?: string,
    readonly fields: ApiFieldError[] = [],
  ) {
    super(code ?? "NO_RESPONSE");
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isLimits(value: unknown): value is Limits {
  return (
    isRecord(value) &&
    isFiniteNumber(value.loanAmountMin) &&
    isFiniteNumber(value.loanAmountMax) &&
    isFiniteNumber(value.loanAmountMaxDecimals) &&
    isFiniteNumber(value.loanTermMonthsMin) &&
    isFiniteNumber(value.loanTermMonthsMax)
  );
}

function parseStatus(body: unknown): QuoteStatus {
  if (
    isRecord(body) &&
    body.available === true &&
    isLimits(body.limits) &&
    isFiniteNumber(body.requestTimeoutSeconds) &&
    body.requestTimeoutSeconds > 0
  ) {
    return {
      available: true,
      limits: body.limits,
      requestTimeoutSeconds: body.requestTimeoutSeconds,
    };
  }
  return { available: false };
}

/** Rejects when the status call fails, which the page reports as unreachable. */
export async function fetchQuoteStatus(): Promise<QuoteStatus> {
  const response = await fetch("/api/v1/quotes/status");
  if (!response.ok) {
    throw new Error(`Status call returned ${response.status}`);
  }
  return parseStatus(await response.json());
}

function isDecimalString(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9]+(\.[0-9]+)?$/.test(value) &&
    Number.isFinite(Number(value))
  );
}

function isQuote(value: unknown): value is Quote {
  return (
    isRecord(value) &&
    typeof value.quoteId === "string" &&
    value.quoteId !== "" &&
    isFiniteNumber(value.commissionRate) &&
    isDecimalString(value.totalCommission)
  );
}

function parseFields(value: unknown): ApiFieldError[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(
    (item): item is ApiFieldError =>
      isRecord(item) &&
      typeof item.field === "string" &&
      typeof item.code === "string",
  );
}

function errorFromBody(body: unknown): ApiError {
  if (
    !isRecord(body) ||
    !isRecord(body.error) ||
    typeof body.error.code !== "string"
  ) {
    return new ApiError();
  }
  const { code, requestId, fields } = body.error;
  return new ApiError(
    code,
    typeof requestId === "string" ? requestId : undefined,
    parseFields(fields),
  );
}

export async function createQuote(
  request: QuoteRequest,
  timeoutSeconds: number,
): Promise<Quote> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutSeconds * 1000);
  try {
    const response = await fetch("/api/v1/quotes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    const body: unknown = await response.json().catch(() => {
      if (controller.signal.aborted) {
        throw new ApiError("VENDOR_TIMEOUT");
      }
      return undefined;
    });
    if (!response.ok) {
      throw errorFromBody(body);
    }
    if (!isQuote(body)) {
      throw new ApiError();
    }
    return body;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw controller.signal.aborted
      ? new ApiError("VENDOR_TIMEOUT")
      : new ApiError();
  } finally {
    clearTimeout(timer);
  }
}
