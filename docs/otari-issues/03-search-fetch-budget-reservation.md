# Per-user budgets: search, fetch and tool-loop charges are invisible, and holds refuse cheap calls

**Where:** hosted otari.ai, service key with a default end-user budget; `POST /api/v1/search`, `POST /api/v1/fetch`, `POST /api/v1/chat/completions` with a managed MCP tool loop

## What happens

Creeping Hunger gives every browser install its own Otari end user with a $0.05 budget. One review makes about 9 requests: a search, two or three fetches, five chat calls (one of them a managed tool loop with our MCP server) and a code run.

On a fresh end user, one review was refused at its last chat call with `403 budget_exceeded`. `GET /end-users?external_id=...` showed `spend: 0.048` after 9 requests. The `usage.cost_usd` on the chat responses added up to about $0.0014.

The rest is spent where the caller cannot see it:

- `/search` and `/fetch` return no cost. Measured through the end user's spend, one `/search` cost $0.007 and one `/fetch` cost $0.01.
- Tool calls inside a managed tool loop (MCP, `otari_web_search`) are not itemised in `usage`.
- Before each request Otari holds an estimate against the budget. When the remaining budget is smaller than the estimate, the request is refused, even if its real cost would fit. A key with about $0.005 left could still make chat calls, but every `/search` and `/fetch` failed.

The 403 says only that the budget is exceeded.

## Steps to reproduce

1. Create a service key with a $0.05 default end-user budget.
2. As end user `u1`, call `/search` once and `/fetch` once.
3. `GET /api/v1/end-users?external_id=u1`. `spend` is about $0.017, and neither response reported a cost.
4. Spend the end user down to about $0.005 left. A cheap chat call still succeeds, and `/search` fails with `budget_exceeded`.

## Expected

- `usage.cost_usd` (or an `Otari-Cost` header) on `/search`, `/fetch` and `/code/execute`, and itemised tool costs in a tool-loop response's `usage`.
- A `budget_exceeded` body that says whether a hold or real spend was the problem, for example `"needed": 0.01, "remaining": 0.005`.
- Docs that list the hold per endpoint next to end-user budgets, so a per-user cap can be sized to the real cost of a request.

## Why it matters

Per-user budgets are meant to be small. Today the hidden charges and holds decide how many requests a user gets, not the costs the API reports.
