import type { Limits } from "./api/client";

const AMOUNT = /^\d+(\.\d+)?$/;

/** The code of the first check the amount text fails, in the backend's order. */
export function checkAmount(text: string, limits: Limits): string | undefined {
  if (text === "") return "REQUIRED";
  if (!AMOUNT.test(text)) return "NOT_A_NUMBER";
  const decimals = text.split(".")[1]?.length ?? 0;
  if (decimals > limits.loanAmountMaxDecimals) return "TOO_MANY_DECIMALS";
  const amount = Number(text);
  if (amount < limits.loanAmountMin || amount > limits.loanAmountMax)
    return "OUT_OF_RANGE";
  return undefined;
}

export function checkTerm(text: string, limits: Limits): string | undefined {
  if (text === "") return "REQUIRED";
  const term = Number(text);
  if (term < limits.loanTermMonthsMin || term > limits.loanTermMonthsMax)
    return "OUT_OF_RANGE";
  return undefined;
}

export function checkRiskBand(value: string): string | undefined {
  return value === "" ? "REQUIRED" : undefined;
}
