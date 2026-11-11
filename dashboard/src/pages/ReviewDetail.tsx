import { useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { BudgetMeter } from "@/components/BudgetMeter"
import { CreepMeter } from "@/components/CreepMeter"
import { JudgeBadges } from "@/components/JudgeBadges"
import { Disclaimer } from "@/components/Disclaimer"
import { Nav } from "@/components/Nav"
import { getBudget, getReview, usd, type Budget, type DoneEvent, type ResultEvent, type ReviewEvent, type StepEvent } from "@/lib/api"

type Detail = { events: ReviewEvent[]; budget: Budget }

function latestSteps(events: ReviewEvent[]) {
  const byId = new Map<string, StepEvent>()
  for (const e of events) if (e.type === "step") byId.set(e.id, { ...byId.get(e.id), ...e })
  return [...byId.values()]
}

const TOOL_STEPS: Partial<Record<StepEvent["id"], string>> = { policy: "Otari /search + /fetch", compute: "Otari /code/execute" }

function fallbackUsed(s: StepEvent) {
  return s.otari?.["otari-fallback"] === "true" || s.otari?.client_fallback === true
}

export function ReviewDetail({ id }: { id: string }) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getReview(id)
      .then(async (r) => setDetail({ events: r.events, budget: await getBudget(r.summary.install_id) }))
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) return <div className="mx-auto max-w-5xl p-6"><Nav /><Alert variant="destructive"><AlertTitle>Could not load review</AlertTitle><AlertDescription>{error}</AlertDescription></Alert></div>
  if (!detail) return <div className="mx-auto flex max-w-5xl flex-col gap-4 p-6"><Nav /><Skeleton className="h-40" /><Skeleton className="h-80" /></div>

  const { events, budget } = detail
  const result = events.find((e): e is ResultEvent => e.type === "result")
  const done = events.find((e): e is DoneEvent => e.type === "done")
  const failure = events.find((e) => e.type === "error")
  const start = events.find((e) => e.type === "start")
  const steps = latestSteps(events)
  const guard = steps.find((s) => s.id === "guard")
  const research = steps.find((s) => s.id === "research")
  const ex = result?.extraction
  const rs = result?.research
  const stats = result?.stats

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <Nav />
      {failure?.type === "error" && <Alert variant="destructive"><AlertTitle>Review failed</AlertTitle><AlertDescription>{failure.message}</AlertDescription></Alert>}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardDescription className="truncate">{start?.type === "start" ? start.url : id}</CardDescription>
            <CardTitle className="text-2xl">{result ? `${result.brand} ${result.product}` : "No verdict"}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <CreepMeter score={result?.score ?? null} />
            {result?.headline && <p className="text-lg font-medium">{result.headline}</p>}
            <div className="flex flex-wrap gap-2">
              {result?.warning_label && <Badge variant="destructive">*Privacy Not Included</Badge>}
              {result?.blocked && <Badge variant="destructive">Prompt injection blocked</Badge>}
            </div>
            <p className="whitespace-pre-line text-sm leading-relaxed">{result?.verdict_md.replace(/^#+\s*/gm, "").replaceAll("**", "")}</p>
            {result?.judge && <JudgeBadges judge={result.judge} />}
          </CardContent>
        </Card>
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardDescription>{done?.billed_usd != null ? "Otari billed for this review" : "Model cost of this review"}</CardDescription>
              <CardTitle className="text-3xl tabular-nums">{usd(done?.billed_usd ?? done?.total_cost_usd)}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {done && `${done.seconds} s end to end. Model calls ${usd(done.total_cost_usd)}${done.billed_usd != null ? ", search and fetch the rest" : ""}.`}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardDescription>Per-user budget for this install, live from Otari</CardDescription></CardHeader>
            <CardContent>
              {budget.budget
                ? <BudgetMeter budget={budget.budget} />
                : <span className="text-sm text-muted-foreground">Not available. The backend key is not a service key, so Otari has no end user for this install.</span>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardDescription>Guardrail</CardDescription><CardTitle>{guard?.status === "error" ? "Injection detected" : "Clean"}</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <span className="text-muted-foreground">{guard?.model} via {guard?.guard_mode}</span>
              {guard?.evidence && <q className="italic">{guard.evidence}</q>}
            </CardContent>
          </Card>
        </div>
      </div>

      {result?.tips && result.tips.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Tips to protect yourself</CardTitle><CardDescription>Written by the judge model from this policy, in the old PNI format.</CardDescription></CardHeader>
          <CardContent><ul className="flex list-disc flex-col gap-1 pl-5 text-sm">{result.tips.map((t) => <li key={t}>{t.replaceAll("**", "")}</li>)}</ul></CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Which model did what</CardTitle><CardDescription>Otari-Model, Otari-Fallback and attempt count as Otari reported them.</CardDescription></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Step</TableHead><TableHead>Model</TableHead><TableHead>Status</TableHead><TableHead>Fallback</TableHead><TableHead className="text-right">Cost</TableHead></TableRow></TableHeader>
            <TableBody>
              {steps.map((s) => (
                <TableRow key={s.id}>
                  <TableCell><div className="font-medium">{s.id}</div><div className="max-w-80 truncate text-muted-foreground">{s.title}</div></TableCell>
                  <TableCell className="font-mono text-xs">{s.otari?.["otari-model"] ?? s.model ?? s.via ?? TOOL_STEPS[s.id] ?? "none"}</TableCell>
                  <TableCell><Badge variant={s.status === "error" ? "destructive" : "secondary"}>{s.status}</Badge></TableCell>
                  <TableCell>{fallbackUsed(s) ? <Badge variant="outline">yes</Badge> : "no"}</TableCell>
                  <TableCell className="text-right tabular-nums">{usd(s.cost_usd)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Red flags from the policy</CardTitle><CardDescription>Extracted by the extractor model with a quote from the policy.</CardDescription></CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {ex?.blocked && <span className="text-muted-foreground">Skipped. The page tried to instruct our models.</span>}
            {ex?.red_flags?.map((f, i) => typeof f === "string"
              ? <p key={i}>{f}</p>
              : <div key={i} className="flex flex-col gap-1"><span className="font-medium">{f.flag}</span>{f.quote && <q className="border-l-2 pl-3 italic text-muted-foreground">{f.quote}</q>}{f.quote_verified === false && <Badge variant="outline">paraphrase, not found verbatim</Badge>}{f.quote_verified && <Badge variant="secondary" className="w-fit">found word for word in the policy</Badge>}</div>)}
            {ex && !ex.blocked && <p className="text-muted-foreground">Sells data: {ex.sells_data}. Ad sharing: {ex.shares_for_ads}. AI training: {ex.ai_training}. Retention: {ex.retention}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Track record</CardTitle><CardDescription>MCP tools: {research?.tool_calls?.map((c) => c.name ?? c.type).join(", ")} ({research?.mcp_mode})</CardDescription></CardHeader>
          <CardContent className="flex flex-col gap-2 text-sm">
            <p>Breaches on Have I Been Pwned: {rs?.breaches?.length ? rs.breaches.map((b) => `${b.name} (${b.date})`).join(", ") : "none on record"}</p>
            <p>ToS;DR grade: <Badge variant="outline">{rs?.tosdr_grade ?? "n/a"}</Badge></p>
            <p>Archived Mozilla PNI review: {rs?.pni_found ? `${rs.pni_people_voted ?? ""}${rs.pni_warning_label ? ", carried the warning label" : ""}` : "none archived"}</p>
            {rs?.pni_summary && <p className="text-muted-foreground">{rs.pni_summary.slice(0, 400)}</p>}
          </CardContent>
        </Card>
      </div>

      {stats && !stats.error && (
        <Card>
          <CardHeader><CardTitle>Fine print, computed in Otari code execution</CardTitle><CardDescription>{stats.reading_minutes} minutes to read, grade level {stats.fk_grade}, {stats.weasel_may_per_1k_words} uses of "may" per 1,000 words.</CardDescription></CardHeader>
          <CardContent className="flex flex-col gap-4 text-sm">
            <div className="flex flex-wrap gap-2">{Object.entries(stats.clause_counts ?? {}).map(([k, v]) => <Badge key={k} variant="secondary">{k.replaceAll("_", " ")}: {v}</Badge>)}</div>
            {stats.diff_vs_archive ? (
              <div className="flex flex-col gap-2">
                <p>Compared with the archived copy (<a className="underline" href={stats.archived_snapshot ?? "#"} target="_blank">Wayback snapshot</a>): {Math.round(stats.diff_vs_archive.similarity * 100)}% similar, {stats.diff_vs_archive.added_sentences} sentences added, {stats.diff_vs_archive.removed_sentences} removed.</p>
                <ul className="flex list-disc flex-col gap-1 pl-5 text-muted-foreground">{stats.diff_vs_archive.new_risky_sentences.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            ) : <p className="text-muted-foreground">No archived copy of this policy to compare against.</p>}
          </CardContent>
        </Card>
      )}
      {done && done.notes.length > 0 && (
        <Alert><AlertTitle>Setup notes</AlertTitle><AlertDescription><ul className="list-disc pl-5">{done.notes.map((n) => <li key={n}>{n}</li>)}</ul></AlertDescription></Alert>
      )}
      <Disclaimer />
    </div>
  )
}
