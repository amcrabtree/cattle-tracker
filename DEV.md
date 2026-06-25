# Cattle Tracker — Developer Notes

## Local development

```bash
cp .env.example .env   # fill in SUPABASE_URL, SUPABASE_KEY, BASE_URL, ALLOWED_EMAILS
make create_environment
make run
```

Server runs at `http://localhost:8000`. Health check: `curl http://localhost:8000/`

Set `BASE_URL=http://localhost:8000` in `.env` when running locally.

---

## Deployment (Render)

### Environment variables
| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase **service role** key (not anon key) |
| `BASE_URL` | Your Render URL e.g. `https://cattle-tracker-2kq1.onrender.com` |
| `ALLOWED_EMAILS` | Comma-separated Gmail addresses allowed to log in |

### Supabase setup
1. Run `migrations/001_initial_schema.sql` in the SQL editor
2. Run `migrations/004_mcp_oauth.sql` in the SQL editor
3. Authentication → Providers → Google → enable and paste your Google OAuth Client ID/Secret
4. Authentication → URL Configuration:
   - **Site URL**: `https://cattle-tracker-2kq1.onrender.com`
   - **Redirect URLs**: `https://cattle-tracker-2kq1.onrender.com/**`

### Google Cloud Console
Credentials → OAuth 2.0 Client ID → Authorized redirect URIs:
- `https://<your-supabase-project>.supabase.co/auth/v1/callback`

### Deploy
```bash
git push
```
Render detects `render.yaml` automatically. Set the four env vars in the dashboard and deploy.

---

## Data import

To import existing records from `old_database/`:

```bash
cd old_database
pip install pandas
jupyter notebook import.ipynb
```

Run all cells — exports `export/animals.csv` and `export/weight_records.csv`.
Import into Supabase via Table Editor → Insert rows → Import data from CSV (`animals` first, then `weight_records`).

---

## Database migrations

| File | Description |
|---|---|
| `migrations/001_initial_schema.sql` | Core tables (animals, weight_records, vaccinations, health_events, breeding_records) |
| `migrations/002_add_bangs_tag.sql` | Adds `bangs_tag` column to animals |
| `migrations/003_add_steer_animal_type.sql` | Adds `steer` to animal_type constraint |
| `migrations/004_mcp_oauth.sql` | OAuth tables for Google login |
