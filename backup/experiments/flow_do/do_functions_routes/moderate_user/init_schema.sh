# ! /bin/bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DO_API_TOKEN" \
  "https://api.digitalocean.com/v2/gen-ai/agents/${AGENT_UUID}/functions" \
  -d moderate_user.json
