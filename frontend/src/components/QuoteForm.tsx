import { useState, type ClipboardEvent, type FormEvent } from "react";
import type {
  ApiFieldError,
  Limits,
  QuoteRequest,
  RiskBand,
} from "../api/client";
import { fieldMessage, type FieldName } from "../messages";
import { checkAmount, checkRiskBand, checkTerm } from "../validation";

type Values = Record<FieldName, string>;
type FieldErrors = Partial<Record<FieldName, string>>;

const EMPTY: Values = { loanAmount: "", loanTermInMonths: "", riskBand: "" };

const DISALLOWED: Partial<Record<FieldName, RegExp>> = {
  loanAmount: /[^0-9.]/g,
  loanTermInMonths: /[^0-9]/g,
};

function isFieldName(name: string): name is FieldName {
  return Object.hasOwn(EMPTY, name);
}

function check(
  field: FieldName,
  value: string,
  limits: Limits,
): string | undefined {
  if (field === "loanAmount") return checkAmount(value, limits);
  if (field === "loanTermInMonths") return checkTerm(value, limits);
  return checkRiskBand(value);
}

/** Server field errors as messages by field; unknown fields and codes are dropped. */
export function usableFieldErrors(
  fields: ApiFieldError[],
  limits?: Limits,
): FieldErrors {
  const errors: FieldErrors = {};
  for (const { field, code } of fields) {
    const message = isFieldName(field)
      ? fieldMessage(field, code, limits)
      : undefined;
    if (isFieldName(field) && message) {
      errors[field] = message;
    }
  }
  return errors;
}

interface QuoteFormProps {
  /** Absent while quotes are unavailable, which greys the form out. */
  limits?: Limits;
  busy: boolean;
  serverErrors: FieldErrors;
  onChange: () => void;
  onClearServerError: (field: FieldName) => void;
  onSubmit: (request: QuoteRequest) => void;
}

export function QuoteForm({
  limits,
  busy,
  serverErrors,
  onChange,
  onClearServerError,
  onSubmit,
}: QuoteFormProps) {
  const [values, setValues] = useState<Values>(EMPTY);
  const [localErrors, setLocalErrors] = useState<FieldErrors>({});

  const errors = { ...serverErrors, ...localErrors };

  function setLocalError(field: FieldName, code: string | undefined) {
    const message = code ? fieldMessage(field, code, limits) : undefined;
    // The key is removed when clear, so a server error on this field still shows after a blur.
    setLocalErrors((current) => {
      const next = { ...current };
      if (message) {
        next[field] = message;
      } else {
        delete next[field];
      }
      return next;
    });
  }

  function change(field: FieldName, raw: string) {
    const value = raw.replace(DISALLOWED[field] ?? "", "");
    setValues((current) => ({ ...current, [field]: value }));
    setLocalError(field, undefined);
    onClearServerError(field);
    onChange();
  }

  function blur(field: FieldName) {
    if (limits) {
      setLocalError(field, check(field, values[field], limits));
    }
  }

  // A paste holding any disallowed character is rejected whole, so it is never silently altered.
  function paste(field: FieldName, event: ClipboardEvent<HTMLInputElement>) {
    const disallowed = DISALLOWED[field];
    if (
      disallowed &&
      event.clipboardData.getData("text").search(disallowed) !== -1
    ) {
      event.preventDefault();
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!limits) {
      return;
    }
    const found: FieldErrors = {};
    for (const field of Object.keys(EMPTY) as FieldName[]) {
      onClearServerError(field);
      const code = check(field, values[field], limits);
      if (code) {
        found[field] = fieldMessage(field, code, limits);
      }
    }
    setLocalErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }
    onSubmit({
      loanAmount: values.loanAmount,
      loanTermInMonths: Number(values.loanTermInMonths),
      riskBand: values.riskBand as RiskBand,
    });
  }

  function describedBy(field: FieldName) {
    return errors[field]
      ? { "aria-invalid": true, "aria-describedby": `${field}-error` }
      : {};
  }

  function fieldError(field: FieldName) {
    return (
      errors[field] && (
        <p className="field-error" id={`${field}-error`}>
          {errors[field]}
        </p>
      )
    );
  }

  return (
    <form onSubmit={submit} noValidate aria-busy={busy}>
      <fieldset
        disabled={busy || !limits}
        className={limits ? undefined : "unavailable"}
      >
        <div className="field">
          <label htmlFor="loanAmount">Loan amount</label>
          <input
            id="loanAmount"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={values.loanAmount}
            onChange={(event) => change("loanAmount", event.target.value)}
            onBlur={() => blur("loanAmount")}
            onPaste={(event) => paste("loanAmount", event)}
            {...describedBy("loanAmount")}
          />
          {fieldError("loanAmount")}
        </div>

        <div className="field">
          <label htmlFor="loanTermInMonths">Term in months</label>
          <input
            id="loanTermInMonths"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            value={values.loanTermInMonths}
            onChange={(event) => change("loanTermInMonths", event.target.value)}
            onBlur={() => blur("loanTermInMonths")}
            onPaste={(event) => paste("loanTermInMonths", event)}
            {...describedBy("loanTermInMonths")}
          />
          {fieldError("loanTermInMonths")}
        </div>

        <div className="field">
          <label htmlFor="riskBand">Risk band</label>
          <select
            id="riskBand"
            value={values.riskBand}
            onChange={(event) => change("riskBand", event.target.value)}
            onBlur={() => blur("riskBand")}
            {...describedBy("riskBand")}
          >
            <option value="">Select…</option>
            <option value="LOW">Low</option>
            <option value="MEDIUM">Medium</option>
            <option value="HIGH">High</option>
          </select>
          {fieldError("riskBand")}
        </div>

        <button type="submit">{busy ? "Generating…" : "Generate Quote"}</button>
      </fieldset>
    </form>
  );
}
