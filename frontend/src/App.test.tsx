import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

const STATUS = {
  available: true,
  requestTimeoutSeconds: 15,
  limits: {
    loanAmountMin: 1,
    loanAmountMax: 10000000,
    loanAmountMaxDecimals: 2,
    loanTermMonthsMin: 1,
    loanTermMonthsMax: 360,
  },
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

/** Routes the status call to `status` and each quote call to the next of `quotes`. */
function mockFetch(
  status: () => Promise<Response>,
  ...quotes: (() => Promise<Response>)[]
) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    if (String(input).endsWith("/quotes/status")) {
      return status();
    }
    return quotes.shift()!();
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const quoteCalls = (fetchMock: ReturnType<typeof mockFetch>) =>
  fetchMock.mock.calls.filter(([input]) => String(input) === "/api/v1/quotes");

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Loan amount"), "1234.5");
  await user.type(screen.getByLabelText("Term in months"), "12");
  await user.selectOptions(screen.getByLabelText("Risk band"), "MEDIUM");
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("on load", () => {
  it("greys out the form with the banner when unavailable", async () => {
    mockFetch(async () =>
      json({ available: false, requestTimeoutSeconds: null, limits: null }),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Commission quotes aren't currently available.",
    );
    expect(screen.getByLabelText("Loan amount")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Generate Quote" }),
    ).toBeDisabled();
  });

  it("treats a failed status call as unavailable", async () => {
    mockFetch(async () => {
      throw new TypeError("network");
    });
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Can't reach the quote service.",
    );
    expect(screen.getByLabelText("Loan amount")).toBeDisabled();
  });

  it("treats malformed limits as unavailable", async () => {
    mockFetch(async () => json({ ...STATUS, limits: { loanAmountMin: "1" } }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Commission quotes aren't currently available.",
    );
  });
});

describe("invalid input", () => {
  it("shows field errors and sends no request", async () => {
    const fetchMock = mockFetch(async () => json(STATUS));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByLabelText("Loan amount");

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(screen.getByText("Enter a loan amount.")).toBeInTheDocument();
    expect(screen.getByText("Enter a loan term.")).toBeInTheDocument();
    expect(screen.getByText("Select a risk band.")).toBeInTheDocument();
    expect(screen.getByLabelText("Loan amount")).toHaveAttribute(
      "aria-describedby",
      "loanAmount-error",
    );
    expect(quoteCalls(fetchMock)).toHaveLength(0);
  });

  it.each([
    ["1.2.3", "Loan amount must be a number."],
    [".5", "Loan amount must be a number."],
    ["1.", "Loan amount must be a number."],
    ["1.100", "Loan amount can have at most 2 decimal places."],
    ["0", "Loan amount must be between $1.00 and $10,000,000.00."],
    ["10000000.01", "Loan amount must be between $1.00 and $10,000,000.00."],
  ])(
    "rejects the amount %s when leaving the field",
    async (amount, message) => {
      mockFetch(async () => json(STATUS));
      const user = userEvent.setup();
      render(<App />);
      await user.type(await screen.findByLabelText("Loan amount"), amount);
      await user.tab();
      expect(screen.getByText(message)).toBeInTheDocument();
    },
  );

  it("rejects an out of range term", async () => {
    mockFetch(async () => json(STATUS));
    const user = userEvent.setup();
    render(<App />);
    await user.type(await screen.findByLabelText("Term in months"), "361");
    await user.tab();
    expect(
      screen.getByText("Term must be between 1 and 360 months."),
    ).toBeInTheDocument();
  });
});

describe("entering values", () => {
  it("filters out disallowed characters as typed", async () => {
    mockFetch(async () => json(STATUS));
    const user = userEvent.setup();
    render(<App />);
    const amount = await screen.findByLabelText("Loan amount");
    await user.type(amount, "1a2,3.5");
    expect(amount).toHaveValue("123.5");
    const term = screen.getByLabelText("Term in months");
    await user.type(term, "1.2");
    expect(term).toHaveValue("12");
  });

  it("rejects a paste with a disallowed character whole", async () => {
    mockFetch(async () => json(STATUS));
    const user = userEvent.setup();
    render(<App />);
    const amount = await screen.findByLabelText("Loan amount");
    await user.click(amount);
    await user.paste("1,5");
    expect(amount).toHaveValue("");
    await user.paste("15.5");
    expect(amount).toHaveValue("15.5");
  });
});

describe("success", () => {
  it("sends numbers and shows the formatted result", async () => {
    const fetchMock = mockFetch(
      async () => json(STATUS),
      async () =>
        json({
          quoteId: "q-1",
          commissionRate: 0.015,
          totalCommission: "1234.50",
        }),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(await screen.findByText("q-1")).toBeInTheDocument();
    expect(screen.getByText("1.50%")).toBeInTheDocument();
    expect(screen.getByText("$1,234.50")).toBeInTheDocument();
    const init = quoteCalls(fetchMock)[0]![1];
    expect(JSON.parse(init?.body as string)).toEqual({
      loanAmount: "1234.5",
      loanTermInMonths: 12,
      riskBand: "MEDIUM",
    });
  });

  it("shows the busy state while waiting and clears the result on edit", async () => {
    let finish: (response: Response) => void = () => {};
    mockFetch(
      async () => json(STATUS),
      () => new Promise((resolve) => (finish = resolve)),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    const button = await screen.findByRole("button", { name: "Generating…" });
    expect(button).toBeDisabled();
    expect(screen.getByLabelText("Loan amount")).toBeDisabled();
    expect(button.closest("form")).toHaveAttribute("aria-busy", "true");

    finish(
      json({ quoteId: "q-1", commissionRate: 0.015, totalCommission: "15.00" }),
    );
    expect(await screen.findByText("q-1")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Term in months"), "0");
    expect(screen.queryByText("q-1")).not.toBeInTheDocument();
  });
});

describe("errors", () => {
  it.each([
    ["QUOTES_UNAVAILABLE", "Commission quotes aren't currently available."],
    [
      "VENDOR_AUTH_FAILED",
      "The quote service rejected our credentials. Please contact support.",
    ],
    [
      "VENDOR_UNAVAILABLE",
      "The quote service is having problems. Please try again.",
    ],
    [
      "VENDOR_TIMEOUT",
      "The quote service took too long to respond. Please try again.",
    ],
    [
      "VENDOR_BAD_RESPONSE",
      "The quote service returned an unexpected response. Please try again.",
    ],
    ["INTERNAL_ERROR", "Something went wrong. Please try again."],
    ["SOMETHING_NEW", "Something went wrong. Please try again."],
  ])("shows the message and reference for %s", async (code, message) => {
    mockFetch(
      async () => json(STATUS),
      async () => json({ error: { code, requestId: "req-1" } }, 502),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(message);
    expect(alert).toHaveTextContent("Reference: req-1");
    expect(screen.getByLabelText("Loan amount")).toHaveValue("1234.5");
  });

  it("shows VALIDATION_FAILED with the server's field errors", async () => {
    mockFetch(
      async () => json(STATUS),
      async () =>
        json(
          {
            error: {
              code: "VALIDATION_FAILED",
              requestId: "req-1",
              fields: [{ field: "loanAmount", code: "OUT_OF_RANGE" }],
            },
          },
          422,
        ),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Please fix the highlighted fields.");
    expect(alert).toHaveTextContent("Reference: req-1");
    expect(
      screen.getByText("Loan amount must be between $1.00 and $10,000,000.00."),
    ).toBeInTheDocument();
  });

  it("shows the generic message for VALIDATION_FAILED with no usable fields", async () => {
    mockFetch(
      async () => json(STATUS),
      async () =>
        json(
          {
            error: {
              code: "VALIDATION_FAILED",
              requestId: "req-1",
              fields: [{ field: "extra", code: "UNKNOWN_FIELD" }],
            },
          },
          422,
        ),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
  });

  it.each([
    [
      "a blank total",
      { quoteId: "q", commissionRate: 0.01, totalCommission: "" },
    ],
    [
      "a numeric total",
      { quoteId: "q", commissionRate: 0.01, totalCommission: 15 },
    ],
    [
      "an exponent",
      { quoteId: "q", commissionRate: 0.01, totalCommission: "1E+3" },
    ],
    [
      "a negative",
      { quoteId: "q", commissionRate: 0.01, totalCommission: "-1" },
    ],
    [
      "an empty ID",
      { quoteId: "", commissionRate: 0.01, totalCommission: "1" },
    ],
  ])("treats a quote with %s as an error", async (_, quote) => {
    mockFetch(
      async () => json(STATUS),
      async () => json(quote),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
    expect(screen.queryByText("Your quote")).not.toBeInTheDocument();
  });

  it("shows the generic message for a code named after an Object.prototype member", async () => {
    mockFetch(
      async () => json(STATUS),
      async () =>
        json({ error: { code: "constructor", requestId: "req-1" } }, 502),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
  });

  it("clears server field errors on an invalid submit", async () => {
    const fetchMock = mockFetch(
      async () => json(STATUS),
      async () =>
        json(
          {
            error: {
              code: "VALIDATION_FAILED",
              requestId: "req-1",
              fields: [{ field: "riskBand", code: "INVALID_VALUE" }],
            },
          },
          422,
        ),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Generate Quote" }));
    expect(await screen.findByText("Select a risk band.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Loan amount"));
    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(screen.getByText("Enter a loan amount.")).toBeInTheDocument();
    expect(screen.queryByText("Select a risk band.")).not.toBeInTheDocument();
    expect(quoteCalls(fetchMock)).toHaveLength(1);
  });

  it("drops server field errors named after Object.prototype members", async () => {
    mockFetch(
      async () => json(STATUS),
      async () =>
        json(
          {
            error: {
              code: "VALIDATION_FAILED",
              requestId: "req-1",
              fields: [{ field: "constructor", code: "REQUIRED" }],
            },
          },
          422,
        ),
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Something went wrong. Please try again.",
    );
  });

  it("leaves out the reference on a network failure", async () => {
    mockFetch(
      async () => json(STATUS),
      async () => {
        throw new TypeError("network");
      },
    );
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong. Please try again.");
    expect(alert).not.toHaveTextContent("Reference");
  });

  it("aborts on timeout and shows the VENDOR_TIMEOUT message", async () => {
    let signal: AbortSignal | undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).endsWith("/quotes/status")) {
        return Promise.resolve(
          json({ ...STATUS, requestTimeoutSeconds: 0.02 }),
        );
      }
      signal = init?.signal ?? undefined;
      return new Promise<Response>((_, reject) => {
        signal?.addEventListener("abort", () =>
          reject(new DOMException("aborted", "AbortError")),
        );
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Generate Quote" }));

    await waitFor(() => expect(signal?.aborted).toBe(true));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "The quote service took too long to respond.",
    );
    expect(alert).not.toHaveTextContent("Reference");
  });
});
