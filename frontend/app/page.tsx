import Link from "next/link";
import { SiteHeader, SiteFooter } from "@/components/Chrome";

const stats = [
  { num: "12 / 12", label: "Official cases passed" },
  { num: "8", label: "Specialised agents" },
  { num: "0", label: "Black-box decisions" },
  { num: "<100ms", label: "Median p50 latency" },
];

const features = [
  {
    label: "Phase one",
    title: "Catch the wrong file before the wrong decision.",
    body: "Document Verification halts the pipeline the moment a prescription is mistaken for a hospital bill. The user is told what they uploaded and what is needed instead — never a generic error.",
  },
  {
    label: "Phase two",
    title: "Every clause in the policy is observed.",
    body: "Coverage, waiting periods, pre-authorisation, dental line-item splits, per-claim caps and fraud signals are evaluated independently. Findings accumulate into the trace; nothing is silently dropped.",
  },
  {
    label: "Phase three",
    title: "Adjudication is deterministic, the math is in the open.",
    body: "Network discount applied first, co-pay applied second, sub-limits respected. Every rupee approved is the result of a function — never a model's intuition. The breakdown ships with the response.",
  },
];

export default function HomePage() {
  return (
    <>
      <SiteHeader />

      <main>
        {/* Hero */}
        <section className="editorial-container py-32 md:py-44 text-center">
          <p className="small-caps mb-8">Plum&nbsp;·&nbsp;AI Pod&nbsp;·&nbsp;Claims Pipeline</p>

          <h1 className="font-serif text-5xl md:text-7xl leading-[1.05] tracking-tight">
            Claims adjudication that
            <br />
            <em className="not-italic text-accent">explains itself.</em>
          </h1>

          <p className="mt-10 max-w-2xl mx-auto text-lg md:text-xl text-muted-foreground leading-relaxed">
            A multi-agent pipeline that reads a member&apos;s documents, applies the
            policy line-by-line, and returns a decision your operations team can
            defend — clause by clause, rupee by rupee.
          </p>

          <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/submit" className="btn btn-primary">
              Submit a claim
              <span aria-hidden>→</span>
            </Link>
            <Link href="/claims" className="btn btn-outline">
              See past decisions
            </Link>
          </div>

          <div className="mt-16 flex items-center justify-center gap-3 text-xs text-muted-foreground font-mono tracking-widest uppercase">
            <span className="h-px w-10 bg-border" />
            Built for{" "}
            <a href="https://www.plumhq.com/" className="link" target="_blank" rel="noreferrer">
              plumhq.com
            </a>
            <span className="h-px w-10 bg-border" />
          </div>
        </section>

        {/* Stats */}
        <section className="editorial-container">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-y-10 md:gap-y-0 border-y border-border py-14">
            {stats.map((s, i) => (
              <div
                key={s.label}
                className={
                  "px-2 md:px-6 text-center " +
                  (i > 0 ? "md:border-l border-border" : "")
                }
              >
                <div className="display-num text-4xl md:text-5xl">{s.num}</div>
                <p className="mt-3 small-caps !text-muted-foreground">{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* The three phases */}
        <section className="editorial-container py-32">
          <div className="section-label"><span>The three phases</span></div>
          <h2 className="font-serif text-4xl md:text-5xl text-center mb-20 leading-tight">
            Three quiet acts. One auditable record.
          </h2>

          <div className="grid md:grid-cols-3 gap-8">
            {features.map((f) => (
              <article key={f.title} className="card card-accent-top card-hover p-10">
                <p className="small-caps mb-5">{f.label}</p>
                <h3 className="font-serif text-2xl mb-4 leading-snug">{f.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Editorial pull quote */}
        <section className="editorial-container py-24">
          <div className="rule" />
          <blockquote className="my-20 text-center max-w-3xl mx-auto">
            <span className="block font-serif text-7xl text-accent leading-none mb-6" aria-hidden>
              &ldquo;
            </span>
            <p className="font-serif text-2xl md:text-3xl leading-snug">
              The only way Plum reaches ten million lives by 2030 — without
              linearly scaling our operations team — is by building systems that
              are reliable, explainable, and genuinely intelligent.
            </p>
            <footer className="mt-8 small-caps">— The assignment brief</footer>
          </blockquote>
          <div className="rule" />
        </section>

        {/* Capabilities asymmetric */}
        <section className="editorial-container py-32">
          <div className="grid grid-cols-1 md:grid-cols-[1.3fr_0.7fr] gap-16 items-start">
            <div>
              <div className="section-label" style={{ justifyContent: "flex-start" }}>
                <span>What it actually does</span>
                <span className="!ml-0 h-px flex-1 bg-border" />
              </div>
              <h2 className="font-serif text-4xl md:text-5xl leading-tight mb-8">
                Eight agents, one decision, full lineage.
              </h2>
              <p className="text-muted-foreground leading-relaxed text-lg mb-6">
                Each agent has one promise. Each promise has a contract.
                Every agent runs inside a circuit-breaker so a Sarvam timeout or a
                malformed JSON doesn&apos;t crash your day — the pipeline degrades,
                drops confidence, and tells you so on the way out.
              </p>
              <Link href="/architecture" className="link">
                Read the full architecture
              </Link>
            </div>

            <ul className="space-y-1">
              {[
                "IntakeAgent",
                "DocumentVerificationAgent",
                "ExtractionAgent",
                "CrossValidationAgent",
                "PolicyCoverageAgent",
                "LimitsAgent",
                "FraudDetectionAgent",
                "AdjudicationAgent",
              ].map((a, i) => (
                <li
                  key={a}
                  className="flex items-baseline justify-between gap-4 py-3 border-b border-border last:border-0"
                >
                  <span className="font-mono text-xs text-muted-foreground">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span className="font-serif text-lg flex-1">{a}</span>
                  <span className="small-caps !text-muted-foreground !text-[0.65rem]">
                    {i < 4 ? "Phase 1" : i < 7 ? "Phase 2" : "Phase 3"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* CTA */}
        <section className="editorial-container py-32">
          <div className="card card-accent-top p-14 md:p-20 text-center bg-[var(--accent-muted)]">
            <p className="small-caps mb-6">Ready when you are</p>
            <h2 className="font-serif text-4xl md:text-5xl leading-tight max-w-2xl mx-auto">
              Try a real test case in under a minute.
            </h2>
            <p className="mt-6 text-muted-foreground max-w-xl mx-auto">
              Pre-loaded with the twelve official scenarios from the assignment.
              Submit one, then watch the trace render line by line.
            </p>
            <div className="mt-10">
              <Link href="/submit" className="btn btn-primary">
                Open the submit form
                <span aria-hidden>→</span>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </>
  );
}
