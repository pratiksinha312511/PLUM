import Link from "next/link";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import { ClaimSummaryCard } from "@/components/Decision";
import { API_BASE, ClaimDecision } from "@/lib/api";

async function fetchAll(): Promise<ClaimDecision[]> {
  try {
    const res = await fetch(`${API_BASE}/claims`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function ClaimsPage() {
  const claims = await fetchAll();

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

        {claims.length === 0 ? (
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
