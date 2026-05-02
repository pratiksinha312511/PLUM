"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import { ClaimSummaryCard } from "@/components/Decision";
import { API_BASE, ClaimDecision } from "@/lib/api";

export default function ClaimsPage() {
  const [claims, setClaims] = useState<ClaimDecision[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/claims`, { cache: "no-store" });
        const data = res.ok ? ((await res.json()) as ClaimDecision[]) : [];
        if (!cancelled) setClaims(data);
      } catch {
        if (!cancelled) setClaims([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <SiteHeader />
      <main className="editorial-container py-20 md:py-28">
        <div className="flex items-end justify-between gap-6 mb-12">
          <div>
            <div className="section-label" style={{ justifyContent: "flex-start" }}>
              <span>Decisions ledger</span>
            </div>
            <h1 className="font-serif text-4xl md:text-6xl leading-tight">
              Every claim, every reason.
            </h1>
            <p className="mt-4 text-muted-foreground max-w-xl">
              An append-only record of decisions produced by the pipeline. Click
              any row to see the full trace.
            </p>
          </div>
          <Link href="/submit" className="btn btn-primary hidden sm:inline-flex">
            New claim →
          </Link>
        </div>

        {claims === null ? (
          <p className="small-caps">Loading…</p>
        ) : claims.length === 0 ? (
          <div className="card p-14 text-center">
            <p className="font-serif text-2xl mb-2">No decisions yet.</p>
            <p className="text-muted-foreground mb-8">
              Submit a claim to populate the ledger.
            </p>
            <Link href="/submit" className="btn btn-primary">
              Submit a claim →
            </Link>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {claims.map((c) => (
              <ClaimSummaryCard key={c.claim_id} d={c} />
            ))}
          </div>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
