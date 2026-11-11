export type OtariMeta = {
  "otari-model"?: string
  "otari-provider"?: string
  "otari-fallback"?: "true" | "false"
  "otari-attempt-count"?: string
  "otari-guardrails"?: { profile: string; status: string; valid: boolean | null }[]
  client_fallback?: boolean
  client_attempts?: number
}

export type StepId = "read" | "scout" | "policy" | "guard" | "extract" | "research" | "compute" | "judge"

export type StepEvent = {
  type: "step"
  id: StepId
  status: "running" | "done" | "error" | "skipped"
  title: string
  model?: string
  otari?: OtariMeta
  cost_usd?: number
  detail?: string
  url?: string
  via?: string
  evidence?: string
  score?: number
  guard_mode?: "otari" | "local"
  mcp_mode?: "otari_managed_mcp" | "local_fallback"
  tool_calls?: { type: string; status: string; name?: string; server?: string }[]
  data?: Record<string, unknown>
}

export type Extraction = {
  blocked?: boolean
  data_collected?: string[]
  sensitive_data?: string[]
  sells_data?: string
  shares_with?: string[]
  shares_for_ads?: string
  law_enforcement?: string
  retention?: string
  ai_training?: string
  ai_training_quote?: string
  opt_outs?: string[]
  red_flags?: (string | { flag: string; quote?: string; quote_verified?: boolean })[]
  good_signs?: string[]
}

export type Research = {
  breaches?: { name: string; date: string; accounts?: number }[]
  tosdr_grade?: string
  tosdr_points?: string[]
  pni_found?: boolean
  pni_warning_label?: boolean
  pni_people_voted?: string
  pni_summary?: string
}

export type Stats = {
  reading_minutes?: number
  fk_grade?: number
  flesch_reading_ease?: number
  clause_counts?: Record<string, number>
  weasel_may_per_1k_words?: number
  archived_snapshot?: string | null
  diff_vs_archive?: {
    similarity: number
    added_sentences: number
    removed_sentences: number
    new_risky_sentences: string[]
  } | null
  error?: string
}

export type ResultEvent = {
  type: "result"
  score: number
  label: string
  headline: string
  warning_label: boolean
  verdict_md: string
  brand: string
  product: string
  policy_url: string | null
  extraction: Extraction
  research: Research
  stats: Stats
  blocked: boolean
}

export type ReviewEvent =
  | StepEvent
  | ResultEvent
  | { type: "start"; review_id: string; url: string; models: Record<string, string> }
  | { type: "done"; total_cost_usd: number; seconds: number; notes: string[]; end_user?: string; end_user_accepted?: boolean }
  | { type: "error"; code: string | null; message: string }

export type ReviewSummary = {
  id: string
  install_id: string
  url: string
  created_at: number
  brand: string | null
  product: string | null
  score: number | null
  label: string | null
  headline: string | null
  blocked: boolean
  total_cost_usd: number | null
  error: string | null
}

export type Budget = { available: true; end_user: Record<string, unknown> | null } | { available: false; reason: string }

// Where the API lives. The dashboard is normally served by the backend itself
// (https://creeping-hunger.onrender.com), so same-origin is the default.
// Override with ?api=http://127.0.0.1:8787 (remembered in localStorage; ?api= with
// no value clears it) or VITE_API_BASE at build time.
function resolveApiBase(): string {
  const q = new URLSearchParams(location.search)
  if (q.has("api")) {
    const v = (q.get("api") ?? "").trim().replace(/\/$/, "")
    if (v) localStorage.setItem("chApiBase", v)
    else localStorage.removeItem("chApiBase")
  }
  return (localStorage.getItem("chApiBase") ?? import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "")
}
export const API_BASE = resolveApiBase()

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(API_BASE + path)
  if (!r.ok) throw new Error(`${path} answered ${r.status}`)
  return r.json() as Promise<T>
}

export const listReviews = () => getJson<ReviewSummary[]>("/api/reviews")
export const getReview = (id: string) => getJson<{ summary: ReviewSummary; events: ReviewEvent[] }>(`/api/reviews/${id}`)
export const getBudget = (installId: string) => getJson<Budget>(`/api/budget/${encodeURIComponent(installId)}`)

export async function runReview(url: string, onEvent: (e: ReviewEvent) => void): Promise<void> {
  const resp = await fetch(API_BASE + "/api/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, install_id: "dashboard" }),
  })
  if (!resp.body) throw new Error(`review answered ${resp.status}`)
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buf += decoder.decode(value, { stream: true })
    const frames = buf.split("\n\n")
    buf = frames.pop() ?? ""
    for (const f of frames) if (f.startsWith("data: ")) onEvent(JSON.parse(f.slice(6)) as ReviewEvent)
  }
}

export const LABELS = ["", "Not creepy", "A little creepy", "Somewhat creepy", "Very creepy", "Super creepy"] as const

export const usd = (n: number | null | undefined) => (n ? `$${n.toFixed(n < 0.01 ? 5 : 4)}` : "$0")
