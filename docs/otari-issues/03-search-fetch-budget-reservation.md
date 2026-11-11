# `/search` and `/fetch` fail with budget_exceeded when less than $0.01 is left, even for cheap calls

**Where:** hosted otari.ai, `POST /api/v1/search`, `POST /api/v1/fetch`

## What happens

A key whose budget had about $0.005 left could still make chat calls, but every `/search` and `/fetch` failed with `403 budget_exceeded`. As far as I can tell the gateway reserves $0.01 before a search or fetch, and refuses when the reservation does not fit, even though a single search costs a fraction of that. The error does not mention the reservation, so it reads as "you are out of money" while chat calls on the same key still work.

## Steps to reproduce

1. Create a key with a small budget, for example $0.05.
2. Spend it down until about $0.005 is left (check `spend` on the key).
3. `POST /api/v1/chat/completions` with a cheap model. It succeeds.
4. `POST /api/v1/search {"query": "test"}`. It fails with `budget_exceeded`.

## Expected

One of:

- Size the reservation to the real cost of the call.
- Say it in the error: "Search reserves $0.01 and this key has $0.005 left."
- Document the per-endpoint reservation next to key and end-user budgets, so a per-user budget can be sized for it.

## Why it matters

Per-user budgets are meant to be small. With a $0.05 daily allowance, a fixed $0.01 hold per search or fetch decides how many reviews a user gets more than the actual cost does.
