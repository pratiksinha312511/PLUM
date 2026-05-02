// In production the frontend is served by FastAPI itself, so we hit
// same-origin /api routes. For local dev, point NEXT_PUBLIC_API_URL at the
// uvicorn server (e.g. http://localhost:8000) and we'll prefix /api there too.
const RAW_BASE = process.env.NEXT_PUBLIC_API_URL || "";
export const API_BASE = `${RAW_BASE.replace(/\/$/, "")}/api`;

export type ClaimCategory =
  | "CONSULTATION"
  | "DIAGNOSTIC"
  | "PHARMACY"
  | "DENTAL"
  | "VISION"
  | "ALTERNATIVE_MEDICINE";

export type DocumentType =
  | "PRESCRIPTION"
  | "HOSPITAL_BILL"
  | "PHARMACY_BILL"
  | "LAB_REPORT"
  | "DIAGNOSTIC_REPORT"
  | "DENTAL_REPORT"
  | "DISCHARGE_SUMMARY"
  | "UNKNOWN";

export type DocumentQuality = "GOOD" | "ACCEPTABLE" | "POOR" | "UNREADABLE";

export type Decision =
  | "APPROVED"
  | "PARTIAL"
  | "REJECTED"
  | "MANUAL_REVIEW"
  | "NEEDS_USER_ACTION";

export interface DocumentInput {
  file_id: string;
  file_name?: string;
  actual_type: DocumentType;
  quality?: DocumentQuality;
  patient_name_on_doc?: string;
  content?: Record<string, unknown>;
}

export interface ClaimSubmission {
  member_id: string;
  policy_id: string;
  claim_category: ClaimCategory;
  treatment_date: string;
  claimed_amount: number;
  hospital_name?: string;
  ytd_claims_amount?: number;
  claims_history?: Array<{ claim_id: string; date: string; amount: number; provider?: string }>;
  documents: DocumentInput[];
  simulate_component_failure?: boolean;
}

export interface TraceStep {
  agent: string;
  status: "passed" | "failed" | "skipped" | "error" | "info";
  summary: string;
  details: Record<string, unknown>;
  duration_ms: number;
  timestamp: string;
}

export interface LineItemDecision {
  description: string;
  claimed_amount: number;
  approved_amount: number;
  status: "APPROVED" | "REJECTED";
  reason?: string;
}

export interface CalculationBreakdown {
  base_amount: number;
  network_discount_percent: number;
  network_discount_amount: number;
  after_network_discount: number;
  copay_percent: number;
  copay_amount: number;
  sub_limit_applied?: number | null;
  final_approved: number;
  notes: string[];
}

export interface UserActionRequired {
  code: string;
  title: string;
  message: string;
  affected_documents: string[];
}

export interface ClaimDecision {
  claim_id: string;
  decision: Decision | null;
  approved_amount: number;
  rejection_reasons: string[];
  line_items: LineItemDecision[];
  calculation: CalculationBreakdown | null;
  confidence_score: number;
  notes: string;
  user_action: UserActionRequired | null;
  fraud_signals: string[];
  degraded: boolean;
  degraded_components: string[];
  trace: TraceStep[];
  submission: ClaimSubmission;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  policy: () => request<Record<string, unknown>>("/policy"),
  submit: (sub: ClaimSubmission) =>
    request<ClaimDecision>("/claims", { method: "POST", body: JSON.stringify(sub) }),
  list: () => request<ClaimDecision[]>("/claims"),
  get: (id: string) => request<ClaimDecision>(`/claims/${id}`),
  upload: async (file: File, actualType: DocumentType): Promise<DocumentInput> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("actual_type", actualType);
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: fd });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status} ${res.statusText}: ${text}`);
    }
    return res.json() as Promise<DocumentInput>;
  },
};

export function inr(n: number | undefined | null): string {
  if (n == null) return "—";
  return `₹${Math.round(n).toLocaleString("en-IN")}`;
}

export function decisionTone(d: Decision | null | undefined) {
  switch (d) {
    case "APPROVED":
      return { label: "Approved", tone: "success" as const };
    case "PARTIAL":
      return { label: "Partial", tone: "warning" as const };
    case "REJECTED":
      return { label: "Rejected", tone: "danger" as const };
    case "MANUAL_REVIEW":
      return { label: "Manual review", tone: "warning" as const };
    case "NEEDS_USER_ACTION":
      return { label: "Action needed", tone: "warning" as const };
    default:
      return { label: "Pending", tone: "muted" as const };
  }
}
