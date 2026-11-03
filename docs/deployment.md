# Deployment (free tier)

| Part | Host | Config in repo |
| --- | --- | --- |
| Database + Auth | Supabase (already set up) | `backend/migrations/` |
| Backend API | Render free web service | `render.yaml` |
| Frontend | Vercel | `frontend/vercel.json` |

The browser loads the frontend from Vercel and calls the API on Render directly
(`VITE_API_BASE_URL`). The API accepts browser requests only from origins listed in
`CORS_ORIGINS`, and it verifies every request's Supabase token.

> Render's free plan sleeps after ~15 minutes without traffic. The first request after
> that takes ~30–60 s while it wakes up. Upgrade the plan to avoid this.

## 0. Before you start

- Code pushed to GitHub (`main` branch).
- All checks pass locally:
  `cd backend && .venv/Scripts/python -m pytest`, then
  `cd frontend && npm test && npm run lint && npm run build`.

## 1. Backend on Render

1. Sign in at https://render.com with GitHub.
2. **New → Blueprint**, pick this repository. Render reads `render.yaml` and proposes the
   `agentforge-api` service.
3. Fill in the variables marked *sync: false*:

   | Key | Value |
   | --- | --- |
   | `DATABASE_URL` | Same Supabase **session pooler** URL as your local `.env` (keep `postgresql+psycopg://` and the `%40`-encoded password) |
   | `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
   | `CORS_ORIGINS` | `["https://placeholder.invalid"]` for now; updated in step 3 |

   (`DATABASE_SSL_MODE=require`, `ENVIRONMENT=production` and `PYTHON_VERSION` are preset.)
4. **Apply**. The first build takes a few minutes. Each start runs `alembic upgrade head`.
5. Check it: open `https://<your-service>.onrender.com/api/health`. It should return `{"status":"ok"}`.

## 2. Frontend on Vercel

1. Sign in at https://vercel.com with GitHub. Click **Add New → Project** and import the repository.
2. **Root Directory:** `frontend` (click *Edit* next to it). Framework preset: Vite.
3. **Environment Variables:**

   | Key | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://<your-service>.onrender.com/api` |
   | `VITE_SUPABASE_URL` | `https://<project-ref>.supabase.co` |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | your `sb_publishable_…` key |

   These are compiled into the public JavaScript bundle; that is expected for these three.
   Never add a secret or `service_role` key here.
4. **Deploy**, then note the URL, e.g. `https://agentforge-xyz.vercel.app`.

## 3. Connect the pieces

1. **Render → agentforge-api → Environment:** set
   `CORS_ORIGINS` = `["https://agentforge-xyz.vercel.app"]`, then save (Render redeploys).
2. **Supabase → Authentication → URL Configuration**
   - Site URL: `https://agentforge-xyz.vercel.app`
   - Redirect URLs: add `https://agentforge-xyz.vercel.app/**`. Keep the localhost entry
     for local development.
3. **Google Cloud → Google Auth Platform → Clients → your client**
   - Authorized JavaScript origins: add `https://agentforge-xyz.vercel.app`
   - Redirect URI stays `https://<project-ref>.supabase.co/auth/v1/callback`.
4. **Google Cloud → Audience:** **Publish app** so any Google account can sign in.

## 4. Verify the live site

- [ ] `https://<render>/api/health` returns `{"status":"ok"}`
- [ ] `https://<render>/api/projects` without a token returns **401**
- [ ] Opening the Vercel URL shows the sign-in page; deep links (e.g. `/projects`) don't 404
- [ ] Google sign-in lands on the dashboard with your avatar
- [ ] Email: create an account, then click the confirmation email link, which should sign you in
- [ ] Create a project, refresh, and it persists. A second account cannot see it.
- [ ] Settings shows the Database as *Ready*

## Email delivery

Supabase's built-in email service is for testing only. It sends a handful of emails per
hour, and they may go to spam. For a public site, configure a custom SMTP provider
(e.g. Resend, Brevo) under **Supabase → Authentication → Emails → SMTP Settings**.
Confirmation and reset links must be opened in the **same browser** that requested them
(PKCE).

## Updating

Push to `main`. Vercel and Render both redeploy automatically, and Render applies any new
migrations on start.
