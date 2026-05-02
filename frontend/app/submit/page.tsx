import { SiteHeader, SiteFooter } from "@/components/Chrome";
import { ClaimForm } from "@/components/ClaimForm";

export default function SubmitPage({
  searchParams,
}: {
  searchParams: { preset?: string };
}) {
  return (
    <>
      <SiteHeader />
      <main className="editorial-container py-20 md:py-28">
        <div className="section-label"><span>Submit a claim</span></div>
        <h1 className="font-serif text-4xl md:text-6xl mb-6 leading-tight">
          A new claim,
          <br />
          <em className="not-italic text-accent">considered carefully.</em>
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl mb-16 leading-relaxed">
          Pick a pre-loaded test case or compose your own. The pipeline accepts
          structured documents directly so you can study any edge case without
          waiting for OCR. Every submission produces a fully-traced decision.
        </p>

        <ClaimForm presetId={searchParams.preset} />
      </main>
      <SiteFooter />
    </>
  );
}
