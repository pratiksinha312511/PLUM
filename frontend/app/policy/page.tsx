"use client";

import { useEffect, useState } from "react";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import { API_BASE, inr } from "@/lib/api";

interface PolicyDoc {
  policy_id: string;
  policy_name: string;
  insurer: string;
  policy_holder: { company_name: string; employee_count: number; renewal_status: string };
  coverage: { sum_insured_per_employee: number; annual_opd_limit: number; per_claim_limit: number };
  opd_categories: Record<string, { sub_limit: number; copay_percent: number; covered: boolean; network_discount_percent?: number }>;
  waiting_periods: { initial_waiting_period_days: number; specific_conditions: Record<string, number> };
  exclusions: { conditions: string[] };
  network_hospitals: string[];
  document_requirements: Record<string, { required: string[]; optional: string[] }>;
  fraud_thresholds: Record<string, number>;
}

export default function PolicyPage() {
  const [p, setP] = useState<PolicyDoc | null | "loading">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/policy`, { cache: "no-store" });
        const data = res.ok ? ((await res.json()) as PolicyDoc) : null;
        if (!cancelled) setP(data);
      } catch {
        if (!cancelled) setP(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (p === "loading") {
    return (
      <>
        <SiteHeader />
        <main className="editorial-container py-32 text-center">
          <p className="small-caps">Loading policy…</p>
        </main>
        <SiteFooter />
      </>
    );
  }

  if (!p) {
    return (
      <>
        <SiteHeader />
        <main className="editorial-container py-32 text-center">
          <p className="small-caps mb-3">Backend offline</p>
          <h1 className="font-serif text-4xl">Could not load policy.</h1>
          <p className="mt-4 text-muted-foreground">
            Start the backend (<code>uvicorn app.main:app --reload</code>) and reload.
          </p>
        </main>
        <SiteFooter />
      </>
    );
  }

  return (
    <>
      <SiteHeader />
      <main className="editorial-container py-20 md:py-28">
        <div className="section-label"><span>Active policy · {p.policy_id}</span></div>
        <h1 className="font-serif text-4xl md:text-6xl leading-tight">
          {p.policy_name}
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          {p.policy_holder.company_name} · {p.policy_holder.employee_count} employees ·{" "}
          insured by {p.insurer}
        </p>

        {/* Coverage stats */}
        <section className="grid sm:grid-cols-3 gap-6 mt-16">
          {[
            { label: "Sum insured", value: inr(p.coverage.sum_insured_per_employee) },
            { label: "Annual OPD limit", value: inr(p.coverage.annual_opd_limit) },
            { label: "Per-claim cap", value: inr(p.coverage.per_claim_limit) },
          ].map((s) => (
            <div key={s.label} className="card card-accent-top p-8 text-center">
              <p className="display-num text-4xl text-accent">{s.value}</p>
              <p className="small-caps mt-3 !text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </section>

        {/* Categories */}
        <section className="mt-24">
          <div className="section-label" style={{ justifyContent: "flex-start" }}>
            <span>Coverage categories</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <div className="card overflow-hidden">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-4 px-6 small-caps !text-muted-foreground">Category</th>
                  <th className="py-4 px-6 small-caps !text-muted-foreground text-right">Sub-limit</th>
                  <th className="py-4 px-6 small-caps !text-muted-foreground text-right">Co-pay</th>
                  <th className="py-4 px-6 small-caps !text-muted-foreground text-right">Network discount</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(p.opd_categories).map(([k, v]) => (
                  <tr key={k} className="border-b border-border last:border-0">
                    <td className="py-4 px-6 font-serif capitalize">{k.replace(/_/g, " ")}</td>
                    <td className="py-4 px-6 text-right font-mono">{inr(v.sub_limit)}</td>
                    <td className="py-4 px-6 text-right font-mono">{v.copay_percent}%</td>
                    <td className="py-4 px-6 text-right font-mono">{v.network_discount_percent ?? 0}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Waiting periods */}
        <section className="mt-24 grid md:grid-cols-2 gap-8">
          <div className="card p-8">
            <p className="small-caps mb-4">Waiting periods</p>
            <ul className="space-y-2 text-foreground/90">
              <li className="flex justify-between border-b border-border pb-2">
                <span>Initial</span>
                <span className="font-mono">{p.waiting_periods.initial_waiting_period_days} days</span>
              </li>
              {Object.entries(p.waiting_periods.specific_conditions).map(([k, v]) => (
                <li key={k} className="flex justify-between border-b border-border pb-2 last:border-0">
                  <span className="capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="font-mono">{v} days</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-8">
            <p className="small-caps mb-4">Global exclusions</p>
            <ul className="space-y-1 text-foreground/90">
              {p.exclusions.conditions.map((c) => (
                <li key={c} className="text-sm">· {c}</li>
              ))}
            </ul>
          </div>
        </section>

        {/* Doc requirements */}
        <section className="mt-24">
          <div className="section-label" style={{ justifyContent: "flex-start" }}>
            <span>Document requirements per category</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(p.document_requirements).map(([cat, req]) => (
              <div key={cat} className="card p-6">
                <h3 className="font-serif text-xl mb-3">{cat.replace(/_/g, " ")}</h3>
                <p className="small-caps mb-2">Required</p>
                <div className="flex flex-wrap gap-2 mb-4">
                  {req.required.map((r) => (
                    <span key={r} className="pill pill-accent !text-[0.6rem]">{r}</span>
                  ))}
                </div>
                {req.optional.length > 0 && (
                  <>
                    <p className="small-caps mb-2 !text-muted-foreground">Optional</p>
                    <div className="flex flex-wrap gap-2">
                      {req.optional.map((o) => (
                        <span key={o} className="pill !text-[0.6rem]">{o}</span>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Network */}
        <section className="mt-24">
          <div className="section-label" style={{ justifyContent: "flex-start" }}>
            <span>Network hospitals</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <div className="flex flex-wrap gap-2">
            {p.network_hospitals.map((h) => (
              <span key={h} className="pill">{h}</span>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
