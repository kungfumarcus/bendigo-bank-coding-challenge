import type { Limits } from "./api/client";

export type FieldName = "loanAmount" | "loanTermInMonths" | "riskBand";

const money = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const percent = new Intl.NumberFormat("en-AU", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const formatMoney = (value: number): string => money.format(value);
export const formatPercent = (value: number): string => percent.format(value);

export const UNREACHABLE_MESSAGE = "Can't reach the quote service.";
export const GENERIC_MESSAGE = "Something went wrong. Please try again.";

const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_FAILED: "Please fix the highlighted fields.",
  QUOTES_UNAVAILABLE: "Commission quotes aren't currently available.",
  VENDOR_AUTH_FAILED:
    "The quote service rejected our credentials. Please contact support.",
  VENDOR_UNAVAILABLE: "The quote service is having problems. Please try again.",
  VENDOR_TIMEOUT:
    "The quote service took too long to respond. Please try again.",
  VENDOR_BAD_RESPONSE:
    "The quote service returned an unexpected response. Please try again.",
  INTERNAL_ERROR: GENERIC_MESSAGE,
};

export function errorMessage(code: string | undefined): string {
  return (code !== undefined && ERROR_MESSAGES[code]) || GENERIC_MESSAGE;
}

/** The message for a field's failed rule, or undefined when the pair is not one we know. */
export function fieldMessage(
  field: FieldName,
  code: string,
  limits: Limits | undefined,
): string | undefined {
  const messages: Record<FieldName, Record<string, string | undefined>> = {
    loanAmount: {
      REQUIRED: "Enter a loan amount.",
      NOT_A_NUMBER: "Loan amount must be a number.",
      TOO_MANY_DECIMALS:
        limits &&
        `Loan amount can have at most ${limits.loanAmountMaxDecimals} decimal places.`,
      OUT_OF_RANGE:
        limits &&
        `Loan amount must be between ${formatMoney(limits.loanAmountMin)} and ${formatMoney(limits.loanAmountMax)}.`,
      INVALID_VALUE: "Enter a valid value.",
    },
    loanTermInMonths: {
      REQUIRED: "Enter a loan term.",
      OUT_OF_RANGE:
        limits &&
        `Term must be between ${limits.loanTermMonthsMin} and ${limits.loanTermMonthsMax} months.`,
      INVALID_VALUE: "Enter a valid value.",
    },
    riskBand: {
      REQUIRED: "Select a risk band.",
      INVALID_VALUE: "Select a risk band.",
    },
  };
  return messages[field][code];
}
