# Web search setup: two settings pages, providers the docs don't list, and a 502 that hides the cause

**Where:** hosted otari.ai, `POST /api/v1/search`, workspace **Tools › Web search**, **Organization › Providers › Web search**

## What happens

1. With web search allowed on the workspace's **Tools › Web search** page (it showed Tavily as the search tool), `POST /api/v1/search` returns:
   `No search tools are configured. Add one on the dashboard's Tools & Guardrails page (or POST /api/v1/search-tools) ...`
2. Search providers are actually configured under **Organization › Providers › Web search**. On hosted otari.ai that list offers Exa, Perplexity, Mojeek, SearXNG, Serply, DeepSeek and Synthetic. The docs mention Tavily and Brave keys, and neither is in the list.
3. We saved a Tavily key with the provider set to DeepSeek. Every search then failed:
   `502 {"detail": "The request could not be completed by the provider"}`
   The only clue was the `otari-error-provider: deepseek` response header and a 404 from DeepSeek behind it.

Adding an Exa key under the organization page fixed search.

## Steps to reproduce

1. On a fresh organization, allow web search on the workspace **Tools › Web search** page.
2. `POST /api/v1/search {"query": "fitbit privacy policy"}`. You get "No search tools are configured".
3. Under **Organization › Providers › Web search**, add any non-DeepSeek API key with the provider set to DeepSeek, and star it.
4. Repeat the search. You get a 502 with no provider name or upstream status in the body.

## Expected

- One place to set up search, or a link from the workspace page to the organization page.
- The "No search tools are configured" message names **Organization › Providers › Web search** on hosted otari.ai.
- The docs list the providers the hosted deployment supports.
- A provider error body that includes the provider and its status, for example `"provider": "deepseek", "upstream_status": 404`.
