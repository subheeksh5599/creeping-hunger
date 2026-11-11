# The `user` field 403 on a non-service key should name the fix

**Where:** hosted otari.ai, `POST /api/v1/chat/completions`

## What happens

On an ordinary API key, sending an end-user id in the standard OpenAI `user` field fails:

```bash
curl -s https://otari.ai/api/v1/chat/completions \
  -H "Otari-Key: $OTARI_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"meta/llama-3.3-70b-instruct","user":"ch-install:1","messages":[{"role":"user","content":"hi"}]}'
```

```json
{"detail": "'user' field does not match the authenticated API key's user"}
```

There is no `code`, and the message does not mention service keys. Per-end-user budgets need a service key, and the **Service key** checkbox on the create-key form is under **Advanced**, closed by default. I found both by reading `end-users.md` and `api-keys.md`.

## Steps to reproduce

1. In the dashboard, open **API keys** and click **Create key** without opening **Advanced**.
2. Run the request above with that key.

## Expected

- A machine-readable code, for example `"code": "user_mismatch"`.
- A message that names the fix: "This key is not a service key. Create a service key to set per-end-user budgets, or change this key's mismatched-user setting."
- The **Service key** option visible on the create-key form, or a note next to the end-user budget settings that they apply only to service keys.

## Why it matters

The `user` field is how every OpenAI-compatible client names an end user, so it is the first thing a developer tries when they want per-user budgets.
