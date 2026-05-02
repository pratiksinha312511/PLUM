"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import {
  CalculationCard,
  DecisionPill,
  LineItemsTable,
  TraceTimeline,
} from "@/components/Decision";
import { API_BASE, ClaimDecision, inr } from "@/lib/api";

function ClaimDetail() {
  const search = useSearchParams();
  const id = search.get("id") || "";
  const [dec, setDec] = useState<ClaimDecision | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "missing" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      setStatus("missing");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/claims/${encodeURIComponent(id)}`, {
          cache: "no-store",
        });
        if (res.status === 404) {
          if (!cancelled) setStatus("missing");
          return;
        }
        if (!res.ok) throw new Error(await res.text());
        const j = (await res.json()) as ClaimDecision;
        if (!cancelled) {
          setDec(j);
          setStatus("ok");
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setStatus("error");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (status === "loading") {
    return (
      <main className="editorial-container py-32 text-center">
        <p className="small-caps">Loading decision…</p>
      </main>
    );
  }

  if (status === "missing") {
    return (
      <main className="editorial-container py-32 text-center">
        <p className="small-caps mb-3">Not found</p>
        <h1 className="font-serif text-4xl mb-6">No decision matches this id.</h1>
        <Link href="/claims" className="btn btn-outline">
          Back to all decisions
        </Link>
      </main>
    );
  }

  if (status === "error" || !dec) {
    return (
      <main className="editorial-container py-32 text-center">
        <p className="small-caps !text-[var(--danger)] mb-3">Failed to load</p>
        <pre className="text-sm text-foreground/80 whitespace-pre-wrap">{error}</pre>
      </main>
    );
  }

  return (
    <main className="editorial-container py-20 md:py-28">
      <Link href="/claims" className="btn btn-ghost !pl-0 mb-6 !text-xs">
        <span aria-hidden>←</span> All decisions
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-6 mb-10">
        <div>
          <p className="small-caps mb-3">{dec.claim_id}</p>
          <h1 className="font-serif text-4xl md:text-6xl leading-tight">
            {dec.submission.member_id} ·{" "}
            <span className="text-muted-foreground">{dec.submission.claim_category}</span>
          </h1>
          <p className="mt-4 text-muted-foreground">
            Treatment date {dec.submission.treatment_date} · Claimed{" "}
            {inr(dec.submission.claimed_amount)}
            {dec.submission.hospital_name ? ` · ${dec.submission.hospital_name}` : ""}
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <DecisionPill decision={dec.decision} />
          <div className="display-num text-5xl text-accent">{inr(dec.approved_amount)}</div>
          <p className="font-mono text-xs text-muted-foreground">
            confidence {dec.confidence_score.toFixed(2)} ·{" "}
            {new Date(dec.created_at).toLocaleString()}
          </p>
        </div>
      </div>

      {dec.user_action && (
        <section className="card card-accent-top !border-t-[var(--warning)] p-8 mb-12 bg-[var(--accent-muted)]">
          <p className="small-caps mb-2">Action required · {dec.user_action.code}</p>
          <h2 className="font-serif text-2xl mb-3">{dec.user_action.title}</h2>
          <p className="text-foreground/90 leading-relaxed">{dec.user_action.message}</p>
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

      {dec.notes && (
        <section className="card p-8 mb-12">
          <p className="small-caps mb-3">Decision notes</p>
          <p className="font-serif text-xl leading-relaxed">{dec.notes}</p>
        </section>
      )}

      {dec.rejection_reasons.length > 0 && (
        <section className="mb-12">
          <p className="small-caps mb-3">Rejection reasons</p>
          <div className="flex flex-wrap gap-2">
            {dec.rejection_reasons.map((r) => (
              <span key={r} className="pill pill-danger">
                {r}
              </span>
            ))}
          </div>
        </section>
      )}

      {dec.fraud_signals.length > 0 && (
        <section className="card p-8 mb-12">
          <p className="small-caps mb-3">Fraud signals</p>
          <ul className="space-y-2">
            {dec.fraud_signals.map((s, i) => (
              <li key={i} className="text-foreground/90">
                · {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      {dec.degraded && (
        <section className="card p-8 mb-12 border-l-2 !border-l-[var(--warning)]">
          <p className="small-caps mb-3">Degraded mode</p>
          <p className="text-foreground/90 mb-2">
            The pipeline produced a decision, but the following components failed and
            were skipped. Confidence has been reduced accordingly.
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            {dec.degraded_components.map((c) => (
              <span key={c} className="pill pill-warning">
                {c}
              </span>
            ))}
          </div>
        </section>
      )}

      <div className="grid lg:grid-cols-2 gap-8 mb-16">
        {dec.calculation && <CalculationCard calc={dec.calculation} />}
        {dec.line_items.length > 0 && <LineItemsTable items={dec.line_items} />}
      </div>

      <section className="mb-16">
        <div className="section-label" style={{ justifyContent: "flex-start" }}>
          <span>Pipeline trace · {dec.trace.length} steps</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <div className="card p-8">
          <TraceTimeline trace={dec.trace} />
        </div>
      </section>

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
  );
}

export default function ClaimDetailPage() {
  return (
    <>
      <SiteHeader />
      <Suspense
        fallback={
          <main className="editorial-container py-32 text-center">
            <p className="small-caps">Loading…</p>
          </main>
        }
      >
        <ClaimDetail />
      </Suspense>
      <SiteFooter />
    </>
  );
}
