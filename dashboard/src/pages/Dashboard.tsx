import { useEffect, useState, type FormEvent } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Nav } from "@/components/Nav"
import { listReviews, runReview, usd, type ReviewSummary } from "@/lib/api"

export function Dashboard() {
  const [rows, setRows] = useState<ReviewSummary[] | null>(null)
  const [url, setUrl] = useState("")
  const [progress, setProgress] = useState<string | null>(null)

  const refresh = () => listReviews().then(setRows)
  useEffect(() => void refresh(), [])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setProgress("Starting")
    let id: string | null = null
    await runReview(url, (ev) => {
      if (ev.type === "start") id = ev.review_id
      if (ev.type === "step") setProgress(ev.title)
      if (ev.type === "error") setProgress(ev.message)
    })
    setProgress(null)
    await refresh()
    if (id) location.hash = `#/review/${id}`
  }

  const spend = rows?.reduce((s, r) => s + (r.total_cost_usd ?? 0), 0) ?? 0
  const blocked = rows?.filter((r) => r.blocked).length ?? 0

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <Nav />
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><CardHeader><CardDescription>Reviews</CardDescription><CardTitle className="text-3xl">{rows?.length ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader><CardDescription>Otari spend</CardDescription><CardTitle className="text-3xl">{usd(spend)}</CardTitle></CardHeader></Card>
        <Card><CardHeader><CardDescription>Pages blocked for prompt injection</CardDescription><CardTitle className="text-3xl">{blocked}</CardTitle></CardHeader></Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Review a product page</CardTitle>
          <CardDescription>Runs the same pipeline as the Firefox sidebar.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit}>
            <FieldGroup>
              <Field orientation="horizontal">
                <FieldLabel htmlFor="url" className="sr-only">Product URL</FieldLabel>
                <Input id="url" type="url" required placeholder="https://www.fitbit.com/global/us/products/trackers/charge6" value={url} onChange={(e) => setUrl(e.target.value)} />
                <Button type="submit" disabled={progress !== null}>
                  {progress !== null && <Spinner data-icon="inline-start" />}
                  Review
                </Button>
              </Field>
              {progress && <FieldDescription>{progress}</FieldDescription>}
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Past reviews</CardTitle></CardHeader>
        <CardContent>
          {rows && rows.length === 0 ? (
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
                  <TableHead>Product</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Install</TableHead>
                  <TableHead>When</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows?.map((r) => (
                  <TableRow key={r.id} className="cursor-pointer" onClick={() => (location.hash = `#/review/${r.id}`)}>
                    <TableCell className="max-w-72">
                      <div className="truncate font-medium">{r.brand ? `${r.brand} ${r.product ?? ""}` : r.url}</div>
                      <div className="truncate text-muted-foreground">{r.headline ?? r.error}</div>
                    </TableCell>
                    <TableCell>
                      {r.score ? <Badge variant={r.score >= 4 ? "destructive" : "secondary"}>{r.score}/5 {r.label}</Badge> : <Badge variant="outline">failed</Badge>}
                      {r.blocked && <Badge variant="outline" className="ml-1">injection blocked</Badge>}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.install_id.slice(0, 8)}</TableCell>
                    <TableCell>{new Date(r.created_at * 1000).toLocaleString()}</TableCell>
                    <TableCell className="text-right tabular-nums">{usd(r.total_cost_usd)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
