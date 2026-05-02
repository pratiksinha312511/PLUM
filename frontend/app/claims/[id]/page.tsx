import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import {
  CalculationCard,
  DecisionPill,
  LineItemsTable,
  TraceTimeline,
} from "@/components/Decision";
import { API_BASE, ClaimDecision, inr } from "@/lib/api";

async function fetchClaim(id: string): Promise<ClaimDecision | null> {
  try {
    const res = await fetch(`${API_BASE}/claims/${id}`, { cache: "no-store" });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  } catch {
    return null;
  }
}

export default async function ClaimDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const dec = await fetchClaim(params.id);
  if (!dec) return notFound();

  return (
    <>
      <SiteHeader />
      <main className="editorial-container py-20 md:py-28">
        <Link href="/claims" className="btn btn-ghost !pl-0 mb-6 !text-xs">
          <span aria-hidden>←</span> All decisions
        </Link>

        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-6 mb-10">
          <div>
            <p className="small-caps mb-3">{dec.claim_id}</p>
            <h1 className="font-serif text-4xl md:text-6xl leading-tight">
              {dec.submission.member_id} ·{" "}
              <span className="text-muted-foreground">
                {dec.submission.claim_category}
              </span>
            </h1>
            <p className="mt-4 text-muted-foreground">
              Treatment date {dec.submission.treatment_date} · Claimed{" "}
              {inr(dec.submission.claimed_amount)}
              {dec.submission.hospital_name ? ` · ${dec.submission.hospital_name}` : ""}
            </p>
          </div>
          <div className="flex flex-col items-end gap-3">
            <DecisionPill decision={dec.decision} />
            <div className="display-num text-5xl text-accent">
              {inr(dec.approved_amount)}
            </div>
            <p className="font-mono text-xs text-muted-foreground">
              confidence {dec.confidence_score.toFixed(2)} ·{" "}
              {new Date(dec.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        {/* Halt message */}
        {dec.user_action && (
          <section className="card card-accent-top !border-t-[var(--warning)] p-8 mb-12 bg-[var(--accent-muted)]">
            <p className="small-caps mb-2">Action required · {dec.user_action.code}</p>
            <h2 className="font-serif text-2xl mb-3">{dec.user_action.title}</h2>
            <p className="text-foreground/90 leading-relaxed">
              {dec.user_action.message}
            </p>
            {dec.user_action.affected_documents.length > 0 && (
              <p className="mt-4 text-sm text-muted-foreground">
                Affected:{" "}
                {dec.user_action.affected_documents.map((id) => (
                  <code key={id} className="font-mono mr-2">
                    {id}
                  </code>
                ))}
              </p>
            )}
          </section>
        )}

        {/* Notes */}
        {dec.notes && (
          <section className="card p-8 mb-12">
            <p className="small-caps mb-3">Decision notes</p>
            <p className="font-serif text-xl leading-relaxed">{dec.notes}</p>
          </section>
        )}

        {/* Rejection reasons */}
        {dec.rejection_reasons.length > 0 && (
          <section className="mb-12">
            <p className="small-caps mb-3">Rejection reasons</p>
            <div className="flex flex-wrap gap-2">
              {dec.rejection_reasons.map((r) => (
                <span key={r} className="pill pill-danger">{r}</span>
              ))}
            </div>
          </section>
        )}

        {/* Fraud signals */}
        {dec.fraud_signals.length > 0 && (
          <section className="card p-8 mb-12">
            <p className="small-caps mb-3">Fraud signals</p>
            <ul className="space-y-2">
              {dec.fraud_signals.map((s, i) => (
                <li key={i} className="text-foreground/90">· {s}</li>
              ))}
            </ul>
          </section>
        )}

        {/* Degraded */}
        {dec.degraded && (
          <section className="card p-8 mb-12 border-l-2 !border-l-[var(--warning)]">
            <p className="small-caps mb-3">Degraded mode</p>
            <p className="text-foreground/90 mb-2">
              The pipeline produced a decision, but the following components
              failed and were skipped. Confidence has been reduced accordingly.
            </p>
            <div className="flex flex-wrap gap-2 mt-3">
              {dec.degraded_components.map((c) => (
                <span key={c} className="pill pill-warning">{c}</span>
              ))}
            </div>
          </section>
        )}

        {/* Calculation + Line items */}
        <div className="grid lg:grid-cols-2 gap-8 mb-16">
          {dec.calculation && <CalculationCard calc={dec.calculation} />}
          {dec.line_items.length > 0 && <LineItemsTable items={dec.line_items} />}
        </div>

        {/* Trace */}
        <section className="mb-16">
          <div className="section-label" style={{ justifyContent: "flex-start" }}>
            <span>Pipeline trace · {dec.trace.length} steps</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <div className="card p-8">
            <TraceTimeline trace={dec.trace} />
          </div>
        </section>

        {/* Raw submission */}
        <section className="mb-16">
          <details className="card p-6">
            <summary className="cursor-pointer small-caps !text-muted-foreground">
              Raw submission payload
            </summary>
            <pre className="mt-4 p-4 bg-muted rounded-md text-xs font-mono overflow-auto whitespace-pre-wrap">
              {JSON.stringify(dec.submission, null, 2)}
            </pre>
          </details>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
