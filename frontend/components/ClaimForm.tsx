"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ClaimSubmission,
  ClaimCategory,
  DocumentInput,
  DocumentType,
  DocumentQuality,
  api,
} from "@/lib/api";

const CATEGORIES: { value: ClaimCategory; label: string }[] = [
  { value: "CONSULTATION", label: "OPD Consultation" },
  { value: "DIAGNOSTIC", label: "Diagnostic / Lab" },
  { value: "PHARMACY", label: "Pharmacy" },
  { value: "DENTAL", label: "Dental" },
  { value: "VISION", label: "Vision" },
  { value: "ALTERNATIVE_MEDICINE", label: "Alternative medicine" },
];

const DOC_TYPES: DocumentType[] = [
  "PRESCRIPTION",
  "HOSPITAL_BILL",
  "PHARMACY_BILL",
  "LAB_REPORT",
  "DIAGNOSTIC_REPORT",
  "DENTAL_REPORT",
  "DISCHARGE_SUMMARY",
];

const QUALITIES: DocumentQuality[] = ["GOOD", "ACCEPTABLE", "POOR", "UNREADABLE"];

interface Preset {
  id: string;
  label: string;
  description: string;
  build: () => ClaimSubmission;
}

const PRESETS: Preset[] = [
  {
    id: "TC001",
    label: "TC001 · Wrong document",
    description: "Two prescriptions for a consultation. Pipeline must halt with a specific message.",
    build: () => ({
      member_id: "EMP001",
      policy_id: "PLUM_GHI_2024",
      claim_category: "CONSULTATION",
      treatment_date: "2024-11-01",
      claimed_amount: 1500,
      documents: [
        { file_id: "F001", file_name: "dr_sharma_prescription.jpg", actual_type: "PRESCRIPTION" },
        { file_id: "F002", file_name: "another_prescription.jpg", actual_type: "PRESCRIPTION" },
      ],
    }),
  },
  {
    id: "TC004",
    label: "TC004 · Clean approval",
    description: "Valid consultation. Should approve ₹1,350 after 10% co-pay.",
    build: () => ({
      member_id: "EMP001",
      policy_id: "PLUM_GHI_2024",
      claim_category: "CONSULTATION",
      treatment_date: "2024-11-01",
      claimed_amount: 1500,
      ytd_claims_amount: 5000,
      documents: [
        {
          file_id: "F007",
          actual_type: "PRESCRIPTION",
          content: {
            doctor_name: "Dr. Arun Sharma",
            doctor_registration: "KA/45678/2015",
            patient_name: "Rajesh Kumar",
            date: "2024-11-01",
            diagnosis: "Viral Fever",
            medicines: ["Paracetamol 650mg", "Vitamin C 500mg"],
          },
        },
        {
          file_id: "F008",
          actual_type: "HOSPITAL_BILL",
          content: {
            hospital_name: "City Clinic, Bengaluru",
            patient_name: "Rajesh Kumar",
            date: "2024-11-01",
            line_items: [
              { description: "Consultation Fee", amount: 1000 },
              { description: "CBC Test", amount: 300 },
              { description: "Dengue NS1 Test", amount: 200 },
            ],
            total: 1500,
          },
        },
      ],
    }),
  },
  {
    id: "TC006",
    label: "TC006 · Dental partial",
    description: "Root canal approved, teeth whitening rejected. Should approve ₹8,000 only.",
    build: () => ({
      member_id: "EMP002",
      policy_id: "PLUM_GHI_2024",
      claim_category: "DENTAL",
      treatment_date: "2024-10-15",
      claimed_amount: 12000,
      documents: [
        {
          file_id: "F011",
          actual_type: "HOSPITAL_BILL",
          content: {
            hospital_name: "Smile Dental Clinic",
            patient_name: "Priya Singh",
            line_items: [
              { description: "Root Canal Treatment", amount: 8000 },
              { description: "Teeth Whitening", amount: 4000 },
            ],
            total: 12000,
          },
        },
      ],
    }),
  },
  {
    id: "TC010",
    label: "TC010 · Network discount",
    description: "Apollo (network) → 20% discount, then 10% co-pay → ₹3,240.",
    build: () => ({
      member_id: "EMP010",
      policy_id: "PLUM_GHI_2024",
      claim_category: "CONSULTATION",
      treatment_date: "2024-11-03",
      claimed_amount: 4500,
      hospital_name: "Apollo Hospitals",
      ytd_claims_amount: 8000,
      documents: [
        {
          file_id: "F019",
          actual_type: "PRESCRIPTION",
          content: {
            doctor_name: "Dr. S. Iyer",
            doctor_registration: "TN/56789/2013",
            patient_name: "Deepak Shah",
            diagnosis: "Acute Bronchitis",
            medicines: ["Amoxicillin 500mg", "Salbutamol Inhaler"],
          },
        },
        {
          file_id: "F020",
          actual_type: "HOSPITAL_BILL",
          content: {
            hospital_name: "Apollo Hospitals",
            patient_name: "Deepak Shah",
            line_items: [
              { description: "Consultation Fee", amount: 1500 },
              { description: "Medicines", amount: 3000 },
            ],
            total: 4500,
          },
        },
      ],
    }),
  },
  {
    id: "TC011",
    label: "TC011 · Component failure",
    description: "Simulates a failed FraudDetectionAgent — pipeline should still produce a decision.",
    build: () => ({
      member_id: "EMP006",
      policy_id: "PLUM_GHI_2024",
      claim_category: "ALTERNATIVE_MEDICINE",
      treatment_date: "2024-10-28",
      claimed_amount: 4000,
      simulate_component_failure: true,
      documents: [
        {
          file_id: "F021",
          actual_type: "PRESCRIPTION",
          content: {
            doctor_name: "Vaidya T. Krishnan",
            doctor_registration: "AYUR/KL/2345/2019",
            diagnosis: "Chronic Joint Pain",
            treatment: "Panchakarma Therapy",
          },
        },
        {
          file_id: "F022",
          actual_type: "HOSPITAL_BILL",
          content: {
            hospital_name: "Ayur Wellness Centre",
            total: 4000,
            line_items: [
              { description: "Panchakarma Therapy (5 sessions)", amount: 3000 },
              { description: "Consultation", amount: 1000 },
            ],
          },
        },
      ],
    }),
  },
];

const EMPTY_DOC = (): DocumentInput => ({
  file_id: `F${Math.floor(Math.random() * 9000 + 1000)}`,
  actual_type: "PRESCRIPTION",
  quality: "GOOD",
  content: {},
});

const BLANK: ClaimSubmission = {
  member_id: "EMP001",
  policy_id: "PLUM_GHI_2024",
  claim_category: "CONSULTATION",
  treatment_date: "2024-11-01",
  claimed_amount: 1500,
  documents: [EMPTY_DOC()],
};

export function ClaimForm({ presetId }: { presetId?: string }) {
  const router = useRouter();
  const [submission, setSubmission] = useState<ClaimSubmission>(BLANK);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [docMeta, setDocMeta] = useState<Record<number, DocMeta>>({});

  // Apply preset if URL specifies one
  useEffect(() => {
    if (!presetId) return;
    const preset = PRESETS.find((p) => p.id === presetId);
    if (preset) {
      setSubmission(preset.build());
      setActivePreset(preset.id);
    }
  }, [presetId]);

  const setField = <K extends keyof ClaimSubmission>(key: K, value: ClaimSubmission[K]) =>
    setSubmission((s) => ({ ...s, [key]: value }));

  const setDoc = (i: number, patch: Partial<DocumentInput>) =>
    setSubmission((s) => ({
      ...s,
      documents: s.documents.map((d, idx) => (idx === i ? { ...d, ...patch } : d)),
    }));

  const setDocContent = (i: number, contentText: string) => {
    let parsed: Record<string, unknown> = {};
    try {
      parsed = contentText.trim() ? JSON.parse(contentText) : {};
    } catch {
      // leave previous
    }
    setDoc(i, { content: parsed });
  };

  const summary = useMemo(() => {
    const docCount = submission.documents.length;
    return `${docCount} document${docCount === 1 ? "" : "s"} · ₹${submission.claimed_amount.toLocaleString("en-IN")}`;
  }, [submission]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const decision = await api.submit(submission);
      router.push(`/claims/detail/?id=${encodeURIComponent(decision.claim_id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-12">
      {/* Presets */}
      <section>
        <div className="section-label" style={{ justifyContent: "flex-start" }}>
          <span>Try a scenario</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {PRESETS.map((p) => (
            <button
              type="button"
              key={p.id}
              onClick={() => {
                setSubmission(p.build());
                setActivePreset(p.id);
              }}
              className={`text-left card card-hover p-4 ${
                activePreset === p.id ? "card-accent-top !border-accent" : ""
              }`}
            >
              <p className="font-mono text-[0.65rem] tracking-widest text-muted-foreground uppercase mb-1">
                {p.id}
              </p>
              <p className="font-serif text-base mb-1">{p.label.split("· ")[1]}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">{p.description}</p>
            </button>
          ))}
        </div>
      </section>

      {/* Member + claim */}
      <section className="grid md:grid-cols-2 gap-6">
        <div>
          <label className="label">Member ID</label>
          <input
            className="input"
            value={submission.member_id}
            onChange={(e) => setField("member_id", e.target.value.toUpperCase())}
          />
        </div>
        <div>
          <label className="label">Policy ID</label>
          <input
            className="input"
            value={submission.policy_id}
            onChange={(e) => setField("policy_id", e.target.value)}
          />
        </div>
        <div>
          <label className="label">Claim category</label>
          <select
            className="select"
            value={submission.claim_category}
            onChange={(e) => setField("claim_category", e.target.value as ClaimCategory)}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Treatment date</label>
          <input
            type="date"
            className="input"
            value={submission.treatment_date}
            onChange={(e) => setField("treatment_date", e.target.value)}
          />
        </div>
        <div>
          <label className="label">Claimed amount (₹)</label>
          <input
            type="number"
            min={0}
            className="input"
            value={submission.claimed_amount}
            onChange={(e) => setField("claimed_amount", Number(e.target.value))}
          />
        </div>
        <div>
          <label className="label">Hospital name (optional)</label>
          <input
            className="input"
            placeholder="e.g. Apollo Hospitals"
            value={submission.hospital_name || ""}
            onChange={(e) => setField("hospital_name", e.target.value)}
          />
        </div>
        <div>
          <label className="label">YTD claims amount (₹)</label>
          <input
            type="number"
            min={0}
            className="input"
            value={submission.ytd_claims_amount || 0}
            onChange={(e) => setField("ytd_claims_amount", Number(e.target.value))}
          />
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-3 cursor-pointer text-sm">
            <input
              type="checkbox"
              className="h-5 w-5 accent-[var(--accent)]"
              checked={submission.simulate_component_failure || false}
              onChange={(e) => setField("simulate_component_failure", e.target.checked)}
            />
            <span>
              <span className="font-serif text-base">Simulate component failure</span>
              <span className="block text-xs text-muted-foreground">
                Forces FraudDetectionAgent to throw — exercises graceful degradation (TC011).
              </span>
            </span>
          </label>
        </div>
      </section>

      {/* Documents */}
      <section>
        <div className="section-label" style={{ justifyContent: "flex-start" }}>
          <span>Documents</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <div className="space-y-6">
          {submission.documents.map((doc, i) => (
            <DocumentCard
              key={i}
              index={i}
              doc={doc}
              docTypes={DOC_TYPES}
              qualities={QUALITIES}
              autoExpand={!!docMeta[i]?.needsReview}
              meta={docMeta[i]}
              showRemove={submission.documents.length > 1}
              onChange={(patch) => setDoc(i, patch)}
              onChangeContent={(text) => setDocContent(i, text)}
              onRemove={() =>
                setSubmission((s) => ({
                  ...s,
                  documents: s.documents.filter((_, idx) => idx !== i),
                }))
              }
              onUpload={async (file) => {
                setDocMeta((m) => ({ ...m, [i]: { uploading: true } }));
                try {
                  const result = await api.upload(file);
                  setSubmission((s) => ({
                    ...s,
                    documents: s.documents.map((d, idx) =>
                      idx === i
                        ? {
                            ...d,
                            file_id: result.file_id,
                            file_name: result.file_name,
                            actual_type: result.actual_type as DocumentType,
                            quality: result.quality as DocumentQuality,
                            patient_name_on_doc:
                              result.patient_name_on_doc || d.patient_name_on_doc,
                            content: result.content || {},
                          }
                        : d
                    ),
                  }));
                  setDocMeta((m) => ({
                    ...m,
                    [i]: {
                      uploading: false,
                      confidence: result.actual_type_confidence,
                      warnings: result.warnings,
                      status: result.extraction_status,
                      needsReview: result.needs_review,
                      uploaded: true,
                    },
                  }));
                } catch (err) {
                  setDocMeta((m) => ({
                    ...m,
                    [i]: {
                      uploading: false,
                      error: err instanceof Error ? err.message : String(err),
                      needsReview: true,
                      uploaded: false,
                    },
                  }));
                }
              }}
            />
          ))}
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              setSubmission((s) => ({ ...s, documents: [...s.documents, EMPTY_DOC()] }));
            }}
          >
            + Add document
          </button>
        </div>
      </section>

      {error && (
        <div className="card border-l-2 border-l-[var(--danger)] p-6 bg-[rgba(179,38,30,0.05)]">
          <p className="small-caps !text-[var(--danger)] mb-2">Submission failed</p>
          <pre className="text-sm whitespace-pre-wrap break-words text-foreground/90">
            {error}
          </pre>
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-border">
        <p className="text-sm text-muted-foreground italic">{summary}</p>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Adjudicating…" : "Submit claim →"}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Per-document upload-first card.
//
// State machine:
//   1. idle      -> show big drop-zone
//   2. uploading -> spinner with "Reading your document..."
//   3. extracted -> compact preview (type pill, patient, quality, confidence)
//                   with "Edit details" expander; auto-expands when needs_review
//   4. error     -> red banner + manual entry surfaced
// ---------------------------------------------------------------------------
type DocMeta = {
  uploading?: boolean;
  uploaded?: boolean;
  confidence?: number;
  warnings?: string[];
  status?: "OK" | "LLM_ERROR" | "INVALID_RESPONSE";
  needsReview?: boolean;
  error?: string;
};

function DocumentCard({
  index,
  doc,
  meta,
  docTypes,
  qualities,
  autoExpand,
  showRemove,
  onChange,
  onChangeContent,
  onUpload,
  onRemove,
}: {
  index: number;
  doc: DocumentInput;
  meta: DocMeta | undefined;
  docTypes: DocumentType[];
  qualities: DocumentQuality[];
  autoExpand: boolean;
  showRemove: boolean;
  onChange: (patch: Partial<DocumentInput>) => void;
  onChangeContent: (text: string) => void;
  onUpload: (file: File) => Promise<void>;
  onRemove: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Auto-open the manual editor whenever extraction needs human review.
  useEffect(() => {
    if (autoExpand) setExpanded(true);
  }, [autoExpand]);

  const uploaded = meta?.uploaded === true;
  const uploading = meta?.uploading === true;
  const fieldCount = Object.keys(doc.content || {}).filter(
    (k) => (doc.content as Record<string, unknown>)?.[k] != null
  ).length;

  function pickFile() {
    inputRef.current?.click();
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void onUpload(f);
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <p className="font-mono text-[0.65rem] tracking-widest text-muted-foreground uppercase">
          Document {index + 1}
        </p>
        {showRemove && (
          <button
            type="button"
            className="btn btn-ghost !text-xs"
            onClick={onRemove}
          >
            Remove
          </button>
        )}
      </div>

      {/* State 1 / 2: drop-zone */}
      {!uploaded && (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={pickFile}
          className={`rounded-lg border border-dashed p-10 text-center cursor-pointer transition-colors ${
            dragOver
              ? "border-accent bg-[var(--accent-muted)]"
              : "border-border bg-cream/40 hover:bg-cream/70"
          }`}
        >
          {uploading ? (
            <div className="space-y-2">
              <p className="small-caps">Reading your document…</p>
              <p className="text-xs text-muted-foreground">
                Sarvam vision is classifying and extracting fields.
                This usually takes 5–20 seconds.
              </p>
            </div>
          ) : (
            <>
              <p className="font-serif text-xl mb-2">
                Drop a prescription, bill, or report here
              </p>
              <p className="text-sm text-muted-foreground mb-4">
                JPEG, PNG, WEBP or PDF · up to 8 MB · we'll detect the type
                and fill the fields automatically.
              </p>
              <button type="button" className="btn btn-outline">
                Choose file
              </button>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onUpload(f);
              e.target.value = "";
            }}
          />
        </div>
      )}

      {/* State 4: error */}
      {meta?.error && (
        <div className="mt-3 rounded-md border-l-2 border-l-[var(--danger)] bg-[rgba(179,38,30,0.05)] p-3 text-sm">
          <p className="small-caps !text-[var(--danger)] mb-1">Upload failed</p>
          <p className="text-foreground/90">{meta.error}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            You can still enter the details manually below.
          </p>
        </div>
      )}

      {/* State 3: preview after a successful upload */}
      {uploaded && (
        <div className="rounded-lg border border-border bg-cream/30 p-4 mb-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-serif text-lg mb-1">
                {doc.file_name || doc.file_id}
              </p>
              <div className="flex flex-wrap gap-2 items-center text-xs">
                <span className="pill">{doc.actual_type}</span>
                <span className="text-muted-foreground">
                  Quality:{" "}
                  <span
                    className={
                      doc.quality === "GOOD"
                        ? "text-emerald-700"
                        : doc.quality === "UNREADABLE"
                        ? "text-[var(--danger)]"
                        : "text-[var(--warning)]"
                    }
                  >
                    {doc.quality}
                  </span>
                </span>
                {meta?.confidence != null && (
                  <span className="text-muted-foreground font-mono">
                    conf {meta.confidence.toFixed(2)}
                  </span>
                )}
              </div>
              {doc.patient_name_on_doc && (
                <p className="text-sm text-foreground/90 mt-2">
                  Patient: <strong>{doc.patient_name_on_doc}</strong>
                </p>
              )}
              <p className="text-xs text-muted-foreground mt-2">
                {fieldCount} field{fieldCount === 1 ? "" : "s"} auto-filled.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-ghost !text-xs"
              onClick={pickFile}
            >
              Replace file
            </button>
          </div>

          {(meta?.warnings?.length || 0) > 0 && (() => {
            const isError = meta?.status && meta.status !== "OK";
            return (
              <div
                className={`mt-3 rounded border-l-2 p-3 text-sm ${
                  isError
                    ? "border-l-[var(--danger)] bg-[rgba(179,38,30,0.05)]"
                    : "border-l-[var(--warning)] bg-[rgba(255,179,0,0.08)]"
                }`}
              >
                <p
                  className={`small-caps mb-1 ${
                    isError ? "!text-[var(--danger)]" : ""
                  }`}
                >
                  {isError ? "Auto-extraction unavailable" : "Please verify"}
                </p>
                <ul className="list-disc list-inside space-y-0.5 text-foreground/90">
                  {meta!.warnings!.map((w, k) => (
                    <li key={k}>{w}</li>
                  ))}
                </ul>
              </div>
            );
          })()}

          <button
            type="button"
            className="btn btn-ghost !text-xs mt-3"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Hide details ▴" : "Edit details ▾"}
          </button>
        </div>
      )}

      {/* Manual editor — always available, expanded after upload only on demand. */}
      {(!uploaded || expanded) && (
        <div className={uploaded ? "border-t border-border pt-4 mt-4" : ""}>
          <div className="grid md:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="label">File ID</label>
              <input
                className="input"
                value={doc.file_id}
                onChange={(e) => onChange({ file_id: e.target.value })}
              />
            </div>
            <div className="md:col-span-2">
              <label className="label">File name</label>
              <input
                className="input"
                value={doc.file_name || ""}
                onChange={(e) => onChange({ file_name: e.target.value })}
                placeholder="prescription.jpg"
              />
            </div>
            <div>
              <label className="label">Quality</label>
              <select
                className="select"
                value={doc.quality}
                onChange={(e) =>
                  onChange({ quality: e.target.value as DocumentQuality })
                }
              >
                {qualities.map((q) => (
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="label">Document type</label>
              <select
                className="select"
                value={doc.actual_type}
                onChange={(e) =>
                  onChange({ actual_type: e.target.value as DocumentType })
                }
              >
                {docTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Patient name on document</label>
              <input
                className="input"
                value={doc.patient_name_on_doc || ""}
                onChange={(e) =>
                  onChange({ patient_name_on_doc: e.target.value })
                }
                placeholder="optional, used for cross-validation"
              />
            </div>
          </div>
          <div>
            <label className="label">Structured content (JSON)</label>
            <textarea
              className="textarea font-mono text-sm"
              value={JSON.stringify(doc.content || {}, null, 2)}
              onChange={(e) => onChangeContent(e.target.value)}
            />
            <p className="text-xs text-muted-foreground mt-2 italic">
              {uploaded
                ? "Edit anything Sarvam got wrong. The pipeline will use what you submit."
                : "Either edit the JSON directly, or upload a file above to have it filled in."}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
