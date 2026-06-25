# Cattle Tracker

MCP server for tracking cattle inventory, weights, vaccinations, health events, and breeding records. Built with Python, Supabase, and the MCP SDK. Deployed on Render.

---

## Connecting via Claude

1. Get to custom integration/connector options: 
 - claude.ai (browser) or Claude mobile app (iOS/Android): **Settings → Integrations → Add custom integration**
 - Claude Desktop (Mac/Windows): Open Claude Desktop → **Customize → Connectors → Add Custom Connector**
2. Enter the name: `CattleTracker` and server URL: `https://cattle-tracker-2kq1.onrender.com/mcp`
3. Click Connect — a browser popup opens asking you to sign in with Google
4. Sign in with your authorized Google account
5. Done — the cattle tracker tools are now available in your conversations

---

## What you can ask Claude

- *"How many active animals are in the herd?"*
- *"Show me the weaning weights for all bulls from October 2025"*
- *"Record that tag 28N received Bovishield Gold today, next due in one year"*
- *"Log a vet visit for tag 58N on June 20th — treated for pinkeye with oxytetracycline"*
- *"Which animals have vaccinations due in the next 30 days?"*
- *"Are there any unresolved health issues in the herd?"*

For batch entries (20–60 animals processed the same day), just describe the whole group — Claude handles it in one tool call.

---

For deployment, local development, and database setup see [DEV.md](DEV.md).
