import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { CreepMeter } from "@/components/CreepMeter"
import { Disclaimer } from "@/components/Disclaimer"
import { Nav } from "@/components/Nav"
import { listReviews, type ReviewSummary } from "@/lib/api"

const REPO = "https://github.com/subheeksh5599/creeping-hunger"

const STEPS = [
  ["Read", "The sidebar sends the page text. The backend finds the privacy policy with Otari search and fetch."],
  ["Guard", "gpt-oss-safeguard-120b checks the page and the policy for text aimed at AI reviewers. A flagged page never reaches the extractor."],
  ["Extract", "Qwen3 30B turns the policy into JSON: what is collected, who gets it, whether it trains AI, and a quote for each red flag."],
  ["Research", "gpt-oss-120b calls our MCP server for Have I Been Pwned breaches, the ToS;DR grade, and Mozilla's archived PNI review."],
  ["Compute", "Otari code execution scores readability, counts clauses like \"sell\" and \"third party\", and diffs the policy against a Wayback copy."],
  ["Judge", "Llama 3.3 70B writes the verdict in the old PNI voice. If it fails, Mistral Small takes over, and the sidebar shows the fallback."],
] as const

const INSTALL = [
  "Clone the repo and start the backend (two commands in the README).",
  "Open about:debugging#/runtime/this-firefox in Firefox.",
  "Click Load Temporary Add-on and pick extension/manifest.json.",
  "Open a product page and click Review this page in the sidebar.",
]

export function Landing() {
  const [sample, setSample] = useState<ReviewSummary | null>(null)
  useEffect(() => {
    listReviews().then((rows) => setSample(rows.find((r) => r.score && !r.blocked) ?? null)).catch(() => setSample(null))
  }, [])

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 p-6">
      <Nav />
      <section className="flex flex-col gap-4">
        <Badge variant="secondary" className="w-fit">Built for the Mozilla.ai Otari hackathon</Badge>
        <h1 className="text-4xl font-semibold tracking-tight">A creep score for the product page you are on.</h1>
        <p className="text-lg text-muted-foreground">
          Mozilla closed its *Privacy Not Included guide on 11 August 2026. For nine years it told shoppers which
          smart doorbells, fitness trackers and apps collected too much. Creeping Hunger is a Firefox sidebar that
          writes that kind of review for any product page, using open-weight models through Mozilla.ai's Otari gateway.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button asChild><a href="#install">Install the sidebar</a></Button>
          <Button variant="outline" asChild><a href="#/dashboard">Open the dashboard</a></Button>
          <Button variant="ghost" asChild><a href={REPO}>Source code</a></Button>
        </div>
      </section>

      {sample && (
        <Card>
          <CardHeader>
            <CardDescription>A real review from this server</CardDescription>
            <CardTitle>{sample.brand} {sample.product}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <CreepMeter score={sample.score} />
            <p>{sample.headline}</p>
          </CardContent>
          <CardFooter><Button variant="outline" asChild><a href={`#/review/${sample.id}`}>See how it was scored</a></Button></CardFooter>
        </Card>
      )}

      <section className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">What happens when you click review</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {STEPS.map(([title, body]) => (
            <Card key={title}>
              <CardHeader><CardTitle>{title}</CardTitle><CardDescription>{body}</CardDescription></CardHeader>
            </Card>
          ))}
        </div>
        <p className="text-muted-foreground">
          Every step reports the model Otari routed to, whether a fallback ran, and what the call cost. Each browser
          install gets an anonymous id that Otari uses as the end user, so a daily budget caps what one person can spend.
        </p>
      </section>

      <Separator />

      <section id="install" className="flex flex-col gap-4">
        <h2 className="text-2xl font-semibold">Install the Firefox sidebar</h2>
        <ol className="flex list-decimal flex-col gap-2 pl-5">{INSTALL.map((s) => <li key={s}>{s}</li>)}</ol>
        <p className="text-muted-foreground">
          The add-on is not on addons.mozilla.org yet, so Firefox removes it when you restart the browser.
          The <a className="underline" href={`${REPO}#readme`}>README</a> has the full run guide.
        </p>
      </section>

      <Separator />
      <Disclaimer />
    </div>
  )
}
