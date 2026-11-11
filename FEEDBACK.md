# Otari feedback

Problems we hit while building Creeping Hunger on the hosted gateway at `https://otari.ai/api/v1`, 11 November 2026. Each section is written so it can be filed as a GitHub issue on `mozilla-ai/otari`.

## 1. Output guardrails are accepted but not enforced

**What happens.** A request can send `"on": ["output"]` on a guardrail entry. The gateway accepts it. The guardrails reference says `output` is "accepted but not enforced yet". Nothing in the response tells the caller the output check did not run: the `Otari-Guardrails` header only lists input results.

**Why it matters.** Our judge model reads evidence that quotes a hostile page on purpose. We wanted an output guardrail on the judge to catch a verdict that repeats an injected instruction, such as "SCORE: 1, endorsed by Mozilla". Today that check has to live in our backend.

**Ask.**
- Until output checks run, refuse `on: ["output"]` with a 400, or add an `Otari-Guardrails` entry with `status: "unavailable"` and `reason: "not_enforced"` for it.
- When output checks ship, say how they work on streamed responses: buffered, checked per chunk, or checked at the end with the stream cut.

## 2. Say whether tool-loop content is checked by guardrails

**What happens.** Guardrails check "what a model is asked before the provider is called". In a managed tool loop, Otari adds `otari_web_fetch` pages, `otari_web_search` results and MCP tool output to the conversation between model calls. The docs do not say whether a block-mode input guardrail runs again on those additions before the next model call. The tools page warns that "fetched content can contain prompt injection" and suggests declaring only tools you would let untrusted content drive.

**Why it matters.** Our research step runs gpt-oss-120b with web search and our MCP server in one loop. A search result or an MCP response is exactly where an injection would enter. We could not tell from the docs whether our guardrail protects that path, so we also scan pages ourselves before any model sees them.

**Ask.**
- State in `guardrails-reference.md` and `tools.md` whether each tool-loop round is checked.
- If it is not, add an option such as `"on": ["input", "tool_results"]` that checks each tool result before it goes back to the model, and returns the tool result as a failed call (`[tool error] guardrail_violation`) instead of failing the whole request.

## 3. The `user` field error does not say what to do

**What happens.** On an ordinary API key, sending `"user": "ch-install:1234"` on `/chat/completions` returns:

```json
{"detail": "'user' field does not match the authenticated API key's user"}
```

There is no `code`, and the message does not mention service keys or the **Mismatched user field** setting. We found both by reading `end-users.md` and `api-keys.md`.

**Why it matters.** Per-user budgets are a rubric feature, and the `user` field is how every OpenAI-compatible client names an end user. A developer who tries it first gets a 403 with no next step.

**Ask.**
- Add `"code": "user_mismatch"` so clients can detect it.
- Name both fixes in the message: create a service key for per-end-user budgets, or set the key's mismatched-user option to accept.

## 4. Smaller friction

- `GET /api/v1/tools` reports `otari_web_search` and `otari_web_fetch` with `"reason": "workspace_disabled"`. It would help to name the switch: Tools, Web search, Allow in workspace.
- `POST /api/v1/code/execute` returns no cost. Chat responses carry `usage.cost_usd`; a code run does not, so a client that shows cost per step has to call `GET /api/v1/usage/requests/{id}` or show nothing.
- The hosted deployment has no guardrails service, so a profile-only guardrail entry comes back `status: "unavailable"`, `reason: "not_configured"`, and in block mode the request fails with a 502. The only way to use a guardrail on otari.ai is a public `url` you host. A sentence on the hosted quickstart would save time.
- Both `https://otari.ai/api/v1` and `https://api.otari.ai/api/v1` work. `https://otari.ai/v1` returns 404. The docs use several base URLs across pages.
