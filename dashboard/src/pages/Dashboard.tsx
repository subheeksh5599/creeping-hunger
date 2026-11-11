import { useEffect, useState, type FormEvent } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Nav } from "@/components/Nav"
import { listReviews, runReview, usd, type ReviewSummary } from "@/lib/api"

const cost = (r: ReviewSummary) => r.billed_usd ?? r.total_cost_usd ?? 0
const shortError = (e: string) => (e.includes("<") ? "Otari gateway error" : e)

function perInstall(rows: ReviewSummary[]) {
  const by = new Map<string, { install: string; reviews: number; spend: number }>()
  for (const r of rows) {
    const row = by.get(r.install_id) ?? { install: r.install_id, reviews: 0, spend: 0 }
    row.reviews += 1
    row.spend += cost(r)
    by.set(r.install_id, row)
  }
  return [...by.values()].sort((a, b) => b.spend - a.spend)
}

export function Dashboard() {
  const [rows, setRows] = useState<ReviewSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [url, setUrl] = useState("")
  const [progress, setProgress] = useState<string | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [running, setRunning] = useState(false)

  const refresh = () => listReviews().then(setRows).catch((e: Error) => setLoadError(e.message))
  useEffect(() => void refresh(), [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setProgress("Starting")
    setRunning(true)
    let id: string | null = null
    let failed = false
    await runReview(url, (ev) => {
      if (ev.type === "start") id = ev.review_id
      if (ev.type === "step") setProgress(ev.title)
      if (ev.type === "error") { failed = true; setProgress(ev.message) }
    }).catch((err: Error) => { failed = true; setProgress(err.message) })
    setRunning(false)
    await refresh()
    if (failed) return
    setProgress(null)
    if (id) location.hash = `#/review/${id}`
  }

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id]))
  const scored = rows?.filter((r) => r.score) ?? []
  const spend = rows?.reduce((s, r) => s + cost(r), 0) ?? 0
  const timed = scored.filter((r) => r.seconds)
  const avgSeconds = timed.length ? timed.reduce((s, r) => s + (r.seconds ?? 0), 0) / timed.length : null
  const stats = [
    ["Reviews", String(scored.length)],
    ["Otari spend", usd(spend)],
    ["Average review time", avgSeconds ? `${Math.round(avgSeconds)} s` : "n/a"],
    ["Injections blocked", String(rows?.filter((r) => r.blocked).length ?? 0)],
    ["Judge fallbacks", String(rows?.filter((r) => r.fallback_used).length ?? 0)],
  ]

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <Nav />
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        {stats.map(([label, value]) => (
          <Card key={label} size="sm">
            <CardHeader><CardDescription>{label}</CardDescription><CardTitle className="text-2xl tabular-nums">{value}</CardTitle></CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Review a product page</CardTitle>
          <CardDescription>Runs the same pipeline as the Firefox sidebar. A page reviewed in the last 24 hours loads from the saved review.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit}>
            <FieldGroup>
              <Field orientation="horizontal">
                <FieldLabel htmlFor="url" className="sr-only">Product URL</FieldLabel>
                <Input id="url" type="url" required placeholder="https://www.fitbit.com/global/us/products/trackers/charge6" value={url} onChange={(e) => setUrl(e.target.value)} />
                <Button type="submit" disabled={running}>
                  {running && <Spinner data-icon="inline-start" />}
                  Review
                </Button>
              </Field>
              {progress && <FieldDescription>{progress}</FieldDescription>}
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Past reviews</CardTitle>
          <CardDescription>Tick two reviews to compare them side by side.</CardDescription>
          <CardAction>
            <Button variant="outline" disabled={picked.length !== 2} onClick={() => (location.hash = `#/compare/${picked[0]}/${picked[1]}`)}>
              Compare {picked.length}/2
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          {loadError ? (
            <p className="text-sm text-destructive">Could not load reviews: {loadError}</p>
          ) : rows && rows.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyTitle>No reviews yet</EmptyTitle>
                <EmptyDescription>Review a page above or from the sidebar.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"><span className="sr-only">Compare</span></TableHead>
                  <TableHead>Product</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead className="text-right">Time</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows?.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => (location.hash = `#/review/${r.id}`)}>
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      {r.score ? <Checkbox aria-label="Pick for comparison" checked={picked.includes(r.id)} onCheckedChange={() => toggle(r.id)} /> : null}
                    </TableCell>
                    <TableCell className="max-w-72">
                      <div className="truncate font-medium">{r.brand ? `${r.brand} ${r.product ?? ""}` : r.url}</div>
                      <div className="truncate text-muted-foreground">{r.headline ?? (r.error && shortError(r.error))}</div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {r.score ? <Badge variant={r.score >= 4 ? "destructive" : "secondary"}>{r.score}/5 {r.label}</Badge> : <Badge variant="outline">failed</Badge>}
                        {r.blocked && <Badge variant="outline">injection blocked</Badge>}
                        {r.fallback_used && <Badge variant="outline">fallback</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap">{new Date(r.created_at * 1000).toLocaleString()}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.seconds ? `${Math.round(r.seconds)} s` : ""}</TableCell>
                    <TableCell className="text-right tabular-nums">{usd(cost(r))}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
      {rows && rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Spend per browser install</CardTitle>
            <CardDescription>Each install is one Otari end user. A service key caps each one with its own budget, and a capped install gets a 403 instead of a review.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead>Install (Otari user)</TableHead><TableHead className="text-right">Reviews</TableHead><TableHead className="text-right">Spend</TableHead></TableRow></TableHeader>
              <TableBody>
                {perInstall(rows).map((p) => (
                  <TableRow key={p.install}>
                    <TableCell className="font-mono text-xs">ch-install:{p.install}</TableCell>
                    <TableCell className="text-right tabular-nums">{p.reviews}</TableCell>
                    <TableCell className="text-right tabular-nums">{usd(p.spend)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
