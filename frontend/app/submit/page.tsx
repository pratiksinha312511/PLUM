"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { SiteHeader, SiteFooter } from "@/components/Chrome";
import { ClaimForm } from "@/components/ClaimForm";

function SubmitInner() {
  const search = useSearchParams();
  const preset = search.get("preset") || undefined;
  return (
    <main className="editorial-container py-20 md:py-28">
      <div className="section-label">
        <span>Submit a claim</span>
      </div>
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

      <ClaimForm presetId={preset} />
    </main>
  );
}

export default function SubmitPage() {
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
        <SubmitInner />
      </Suspense>
      <SiteFooter />
    </>
  );
}
