import type { Quote } from "../api/client";
import { formatMoney, formatPercent } from "../messages";

export function QuoteResult({ quote }: { quote: Quote }) {
  return (
    <section className="result" aria-label="Quote">
      <h2>Your quote</h2>
      <dl>
        <dt>Quote ID</dt>
        <dd className="quote-id">{quote.quoteId}</dd>
        <dt>Commission rate</dt>
        <dd>{formatPercent(quote.commissionRate)}</dd>
        <dt>Total commission</dt>
        <dd>{formatMoney(quote.totalCommission)}</dd>
      </dl>
    </section>
  );
}
