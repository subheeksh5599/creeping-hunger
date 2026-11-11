# Otari feedback

I built Creeping Hunger on the hosted gateway at `https://otari.ai/api/v1` on 11 November 2026. Every model call, search, fetch, code run and budget in the app goes through Otari. These answers come from that day of building. Each bug below has steps to reproduce, and the three worst are drafted as GitHub issues in [`docs/otari-issues/`](docs/otari-issues/).

## When were you most tempted to skip Otari and call the provider directly? What happened?

Web search. It cost me more time than any other feature.

`POST /api/v1/search` answered `No search tools are configured`. My workspace's **Tools › Web search** page already showed Tavily as enabled, and the docs talk about Tavily and Brave keys, so I had a Tavily key ready. Search providers are set somewhere else, under **Organization › Providers › Web search**, and on hosted otari.ai that list has only Exa, Perplexity, Mojeek, SearXNG, Serply, DeepSeek and Synthetic. No Tavily. We saved the Tavily key under DeepSeek, the closest-sounding option. Every search then failed with a 502 that said only "could not be completed by the provider". The cause was in one response header, `otari-error-provider: deepseek`, plus a 404 from DeepSeek. Switching to an Exa key fixed it.

At that point a direct call to Tavily's API with my own key would have taken ten lines. I kept going because search and fetch are scored here, and because Otari's `/fetch` was already working.

The second time was mid-review 504s. Some calls came back as a CloudFront HTML error page ("The request could not be satisfied") instead of JSON. My client tried to parse it and the raw HTML ended up in the sidebar. A direct provider call would not have had that extra hop.

## What did you end up building yourself that Otari should've done for you?

- **Retry on gateway errors.** `backend/otari.py` retries once on 502, 503, 504 and connection timeouts. It turns an HTML error body into a short `gateway_error`. The pipeline finishes a review without the research or compute step when those still fail. A gateway that already does provider fallback could retry its own edge timeouts, and should always answer in JSON.
- **The guardrail service.** Hosted Otari has no guardrail backend (`GET /tool-settings/guardrails/profiles` returns `available: false`), so a profile-only guardrail fails closed with a 502. I wrote a prompt-injection checker (`backend/guard.py`, regex plus `gpt-oss-safeguard-120b`) and serve it at `/guardrail/validate` so Otari can call it by `url`. Without a public URL, the backend runs the same check itself before the extractor.
- **A daily per-user budget.** I wanted "a few free reviews per browser per day". End-user budgets reset monthly by default (`budget_started_at 2026-11-01`, `next_budget_reset_at 2026-12-01` on our end user), and I could not find a daily period for a service key's default end-user budget. The sidebar now shows spend against the limit and the real reset date instead of promising "tomorrow".
- **Remaining budget for the UI.** The `Otari-End-User-Budget` response header carries the budget's id, not what is left. To show "you have used $0.03 of $0.05" I call `GET /end-users?external_id=...` after each review and read `spend`. The limit itself I had to put in an env var, because `GET /budgets/{id}` refuses an API key ("Invalid master key").
- **The real cost of a review.** Chat responses carry `usage.cost_usd`, but `/search`, `/fetch` and `/code/execute` return no cost at all. I measured it through the end-user spend: one `/search` moved it by $0.007 and one `/fetch` by $0.01. A Fitbit review whose model calls cost $0.0052 was billed about $0.04, mostly for fetches. The backend now reads the end user's spend before and after each review and shows that difference as what Otari billed.
- **MCP fallback.** Otari calls MCP servers from its own network, so a local MCP server does nothing during development. The backend runs the same tool functions in-process when `MCP_PUBLIC_URL` is unset, and the UI labels that `local_fallback`.

## If the rules hadn't required Otari, would you have continued using Otari? Why or why not?

Yes, for this app, with two conditions.

The reasons to stay are real. One key gave me five open-weight models from four labs, and I switched models by changing a string. The routing policy gave me judge fallback without code. The `Otari-Model`, `Otari-Fallback` and `Otari-Attempt-Count` headers made the fallback something I can show users in the sidebar. A service key plus the `user` field gave every browser install its own spend cap, which is the only reason I can hand out a free AI tool without a login. The managed MCP tool loop saved me writing my own tool-calling loop. Code execution saved me running a sandbox.

The conditions are search setup and error clarity. If the search problem above had happened on day one of a real project with no rubric, I would have called Tavily directly and maybe never come back for the other features. Clear errors would have saved most of the time I lost: "this key is not a service key", "DeepSeek is not a search provider", "this budget needs $0.01 free to start a search".

## Bugs and friction, with repro steps

1. **The `user` field error does not say what to do.** Create an ordinary API key. `POST /chat/completions` with `"user": "ch-install:1"`. You get `403 {"detail": "'user' field does not match the authenticated API key's user"}` with no `code` and no hint. The fix is a service key, and the **Service key** checkbox is hidden under **Advanced** on the create-key form. Draft: [`docs/otari-issues/01-user-field-error.md`](docs/otari-issues/01-user-field-error.md).
2. **Search provider setup is in two places and errors are opaque.** On hosted otari.ai, open the workspace's **Tools › Web search** (shows Tavily). Call `POST /search`: "No search tools are configured". Add a key under **Organization › Providers › Web search** with provider DeepSeek. Call `/search`: 502 "could not be completed by the provider", with the real cause only in the `otari-error-provider` header. Draft: [`docs/otari-issues/02-search-provider-setup.md`](docs/otari-issues/02-search-provider-setup.md).
3. **`/search` and `/fetch` reserve $0.01 even when the call costs far less.** Give a key a budget with about $0.005 left. `POST /search` fails with `budget_exceeded`, though a search costs a fraction of a cent. The error does not say the reservation is the problem. Draft: [`docs/otari-issues/03-search-fetch-budget-reservation.md`](docs/otari-issues/03-search-fetch-budget-reservation.md).
4. **Gateway errors sometimes arrive as CloudFront HTML.** Under load, a `/chat/completions` call returned `504` with `content-type: text/html` and a CloudFront "The request could not be satisfied" page. Clients that expect JSON break. It happened intermittently during a day of testing.
5. **Routing policies take a bare name only.** `"model": "creeping-hunger-judge"` works. `"model": "policy/creeping-hunger-judge"`, which looks like the provider/model form used everywhere else, is rejected. One line in the routing docs would fix this.
6. **End-user budgets default to monthly.** A service key's default end-user budget reset on the 1st of the month. A consumer app usually wants a daily allowance.
7. **Output guardrails are accepted but not enforced.** A guardrail entry with `"on": ["output"]` is accepted. The reference says output is "accepted but not enforced yet", and the `Otari-Guardrails` header reports nothing for it. I wanted an output check on the judge to catch a verdict that repeats an injected instruction. A 400, or a `status: "not_enforced"` entry, would be honest.
8. **Unclear whether tool-loop content is guardrail-checked.** The docs do not say whether a block-mode input guardrail runs again on `otari_web_search` results and MCP tool output inside a managed tool loop. That is where an injection would enter, so I scan pages myself before any model sees them.
9. **Smaller things.** `GET /tools` reports `"reason": "workspace_disabled"` without naming the switch (Tools, Web search, Allow in workspace). `/search`, `/fetch` and `/code/execute` return no cost. Both `https://otari.ai/api/v1` and `https://api.otari.ai/api/v1` work while `https://otari.ai/v1` is a 404, and the docs use several base URLs.
