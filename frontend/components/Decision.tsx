import { ClaimDecision, decisionTone, inr } from "@/lib/api";
import Link from "next/link";

const toneClass: Record<string, string> = {
  success: "pill-success",
  danger: "pill-danger",
  warning: "pill-warning",
  muted: "",
};

export function DecisionPill({ decision }: { decision: ClaimDecision["decision"] }) {
  const t = decisionTone(decision);
  return <span className={`pill ${toneClass[t.tone]}`}>{t.label}</span>;
}

const statusDot: Record<string, string> = {
  passed: "bg-[var(--success)]",
  failed: "bg-[var(--danger)]",
  error: "bg-[var(--danger)]",
  skipped: "bg-[var(--muted-foreground)]",
  info: "bg-[var(--accent)]",
};

export function TraceTimeline({ trace }: { trace: ClaimDecision["trace"] }) {
  return (
    <ol className="relative border-l border-border ml-3">
      {trace.map((step, i) => (
        <li key={i} className="pl-8 pb-8 relative">
          <span
            className={`absolute -left-[7px] top-1.5 h-3 w-3 rounded-full border-2 border-background ${
              statusDot[step.status] || "bg-muted-foreground"
            }`}
          />
          <div className="flex flex-wrap items-center gap-3 mb-1">
            <span className="font-serif text-lg">{step.agent}</span>
            <span className="small-caps !text-[0.65rem] !text-muted-foreground">
              {step.status}
            </span>
            {step.duration_ms ? (
              <span className="font-mono text-xs text-muted-foreground">
                {step.duration_ms.toFixed(1)}ms
              </span>
            ) : null}
          </div>
          <p className="text-foreground/90">{step.summary}</p>
          {step.details && Object.keys(step.details).length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-xs font-mono uppercase tracking-widest text-muted-foreground hover:text-accent transition-colors select-none">
                Details
              </summary>
              <pre className="mt-3 p-4 rounded-md bg-muted text-xs overflow-auto border border-border whitespace-pre-wrap break-words">
                {JSON.stringify(step.details, null, 2)}
              </pre>
            </details>
          )}
        </li>
      ))}
    </ol>
  );
}

export function CalculationCard({ calc }: { calc: NonNullable<ClaimDecision["calculation"]> }) {
  const rows: Array<[string, string, string?]> = [
    ["Base amount", inr(calc.base_amount)],
  ];
  if (calc.network_discount_amount) {
    rows.push([
      `Network discount (${calc.network_discount_percent}%)`,
      `− ${inr(calc.network_discount_amount)}`,
      "applied first",
    ]);
    rows.push(["Subtotal after network discount", inr(calc.after_network_discount)]);
  }
  if (calc.copay_amount) {
    rows.push([
      `Member co-pay (${calc.copay_percent}%)`,
      `− ${inr(calc.copay_amount)}`,
      "applied on post-discount amount",
    ]);
  }
  if (calc.sub_limit_applied) {
    rows.push([`Capped at sub-limit`, inr(calc.sub_limit_applied)]);
  }
  return (
    <div className="card p-8">
      <p className="small-caps mb-4">Financial breakdown</p>
      <table className="w-full text-left">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              <td className="py-3 align-top">
                <span className="font-serif text-base">{r[0]}</span>
                {r[2] && (
                  <div className="text-xs text-muted-foreground italic">{r[2]}</div>
                )}
              </td>
              <td className="py-3 text-right font-mono">{r[1]}</td>
            </tr>
          ))}
          <tr>
            <td className="pt-5 align-top">
              <span className="font-serif text-lg">Final approved</span>
            </td>
            <td className="pt-5 text-right font-serif text-3xl text-accent">
              {inr(calc.final_approved)}
            </td>
          </tr>
        </tbody>
      </table>
      {calc.notes.length > 0 && (
        <ul className="mt-6 space-y-1 text-sm text-muted-foreground">
          {calc.notes.map((n, i) => (
            <li key={i}>· {n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function LineItemsTable({
  items,
}: {
  items: ClaimDecision["line_items"];
}) {
  if (!items.length) return null;
  return (
    <div className="card p-8">
      <p className="small-caps mb-4">Line-item breakdown</p>
      <table className="w-full text-left">
        <thead>
          <tr className="border-b border-border">
            <th className="py-3 small-caps !text-muted-foreground">Description</th>
            <th className="py-3 small-caps !text-muted-foreground text-right">Claimed</th>
            <th className="py-3 small-caps !text-muted-foreground text-right">Approved</th>
            <th className="py-3 small-caps !text-muted-foreground">Status</th>
          </tr>
        </thead>
        <tbody>
          {items.map((li, i) => (
            <tr key={i} className="border-b border-border last:border-0 align-top">
              <td className="py-4">
                <div className="font-serif">{li.description}</div>
                {li.reason && (
                  <div className="text-xs text-muted-foreground mt-1 italic">
                    {li.reason}
                  </div>
                )}
              </td>
              <td className="py-4 text-right font-mono">{inr(li.claimed_amount)}</td>
              <td className="py-4 text-right font-mono">{inr(li.approved_amount)}</td>
              <td className="py-4">
                <span
                  className={`pill ${
                    li.status === "APPROVED" ? "pill-success" : "pill-danger"
                  }`}
                >
                  {li.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ClaimSummaryCard({ d }: { d: ClaimDecision }) {
  return (
    <Link
      href={`/claims/${d.claim_id}`}
      className="card card-hover p-6 block group"
    >
      <div className="flex items-baseline justify-between mb-3">
        <span className="font-mono text-xs text-muted-foreground">
          {d.claim_id}
        </span>
        <DecisionPill decision={d.decision} />
      </div>
      <h3 className="font-serif text-xl mb-2 group-hover:text-accent transition-colors">
        {d.submission.member_id} · {d.submission.claim_category}
      </h3>
      <p className="text-sm text-muted-foreground">
        Treatment&nbsp;{d.submission.treatment_date} · Claimed{" "}
        {inr(d.submission.claimed_amount)} · Approved{" "}
        <span className="text-accent font-medium">{inr(d.approved_amount)}</span>
      </p>
      <div className="mt-4 flex items-center justify-between text-xs">
        <span className="font-mono text-muted-foreground">
          conf {d.confidence_score.toFixed(2)}
        </span>
        {d.degraded && (
          <span className="pill pill-warning !text-[0.6rem]">degraded</span>
        )}
      </div>
    </Link>
  );
}
