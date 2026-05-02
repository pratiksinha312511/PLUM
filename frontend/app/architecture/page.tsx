import Link from "next/link";
import { SiteHeader, SiteFooter } from "@/components/Chrome";

const phases = [
  {
    title: "Phase 1 · Gate",
    body: "IntakeAgent · DocumentVerificationAgent · ExtractionAgent · CrossValidationAgent. If anything is wrong with the input itself, the pipeline stops here with a single, specific, actionable user message — not a generic error.",
  },
  {
    title: "Phase 2 · Observe",
    body: "PolicyCoverageAgent · LimitsAgent · FraudDetectionAgent. Three independent observers. They never set the final decision — they accumulate findings into the trace.",
  },
  {
    title: "Phase 3 · Adjudicate",
    body: "AdjudicationAgent is the only component allowed to set Decision and approved_amount. Math is deterministic: network discount first, co-pay second, sub-limits respected.",
  },
];

const principles = [
  {
    label: "01",
    title: "Determinism over magic.",
    body: "LLMs read documents. Code makes decisions. Every rupee paid is the result of a function applied to data from policy_terms.json — never a model's intuition.",
  },
  {
    label: "02",
    title: "Explainability is not a feature.",
    body: "It's the contract. Every agent appends a structured TraceStep. The frontend renders them as a timeline. An ops engineer can reconstruct any decision from the response alone.",
  },
  {
    label: "03",
    title: "Failure is a first-class state.",
    body: "Every agent runs inside safe_run. A Sarvam timeout doesn't crash a request — it appends an error step, drops confidence, marks the decision degraded, and lets the rest of the pipeline run.",
  },
];

export default function ArchitecturePage() {
  return (
    <>
      <SiteHeader />
      <main className="editorial-container py-20 md:py-28">
        <div className="section-label"><span>Architecture · v1.0.0</span></div>
        <h1 className="font-serif text-5xl md:text-7xl leading-[1.05] tracking-tight">
          Eight agents.
          <br />
          <em className="not-italic text-accent">One auditable record.</em>
        </h1>
        <p className="mt-8 max-w-2xl text-lg text-muted-foreground leading-relaxed">
          A short tour of the pipeline. The full design rationale lives in{" "}
          <code className="font-mono">docs/ARCHITECTURE.md</code> and the
          per-agent contracts in <code className="font-mono">docs/COMPONENT_CONTRACTS.md</code>.
        </p>

        {/* Three principles */}
        <section className="mt-32 grid md:grid-cols-3 gap-8">
          {principles.map((p) => (
            <article key={p.label} className="card card-accent-top p-10">
              <p className="display-num text-4xl text-accent mb-4">{p.label}</p>
              <h3 className="font-serif text-2xl mb-3 leading-snug">{p.title}</h3>
              <p className="text-muted-foreground leading-relaxed">{p.body}</p>
            </article>
          ))}
        </section>

        {/* Phases */}
        <section className="mt-32">
          <div className="section-label" style={{ justifyContent: "flex-start" }}>
            <span>The three phases</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <ol className="space-y-12">
            {phases.map((p, i) => (
              <li key={p.title} className="grid grid-cols-[auto_1fr] gap-8 items-baseline">
                <div className="display-num text-6xl text-accent">{i + 1}</div>
                <div className="border-t-2 border-accent pt-4">
                  <h3 className="font-serif text-3xl mb-3">{p.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{p.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        {/* Trade-offs */}
        <section className="mt-32 grid md:grid-cols-[1.3fr_0.7fr] gap-12 items-start">
          <div>
            <div className="section-label" style={{ justifyContent: "flex-start" }}>
              <span>Trade-offs I made deliberately</span>
              <span className="h-px flex-1 bg-border" />
            </div>
            <ul className="space-y-6 text-foreground/90">
              <li><strong className="font-serif text-lg">No file uploads in this build.</strong> The eval needs deterministic inputs. The Sarvam path stays wired for the moment a real upload endpoint is added.</li>
              <li><strong className="font-serif text-lg">In-memory store.</strong> The repository interface mirrors what a SQLAlchemy adapter would expose; the swap is mechanical.</li>
              <li><strong className="font-serif text-lg">Per-claim cap interpretation.</strong> The policy file lists 5,000 as the per-claim cap; this is enforced for OPD consultations only. Dental, pharmacy, and diagnostics have their own (higher) sub-limits — capping them at 5,000 would invalidate those allowances. Documented at the call site.</li>
              <li><strong className="font-serif text-lg">Sub-limit treated as annual.</strong> Per-category sub-limit is treated as the annual cap, not a per-claim cap. Annual usage tracking is the obvious next step (per-member-per-category ledger).</li>
            </ul>
          </div>
          <aside className="card p-8 sticky top-28">
            <p className="small-caps mb-4">At 10× load, I would add</p>
            <ul className="space-y-3 text-sm">
              <li>Postgres for ClaimDecisions; trace as JSONB</li>
              <li>Async OCR via S3 + worker queue</li>
              <li>Per-member ledgers for true sub-limit enforcement</li>
              <li>Idempotency-Key support on POST /claims</li>
              <li>OpenTelemetry for trace + agent latency histograms</li>
              <li>Versioned policy config service (decision records its policy version)</li>
              <li>Behavioural fraud model surfaced to ops, never to auto-decisions</li>
            </ul>
          </aside>
        </section>

        <section className="mt-32 text-center">
          <Link href="/submit" className="btn btn-primary">
            Try it now →
          </Link>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
