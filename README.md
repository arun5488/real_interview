# Real Interview

Flask application that guides a candidate from account setup through resume upload, job application, and an AI-driven mock interview. The web UI is served from the same server as the backend.

**Live site:** [https://real-interview-lpd6.onrender.com/](https://real-interview-lpd6.onrender.com/)  
**Admin dashboard:** [https://real-interview-lpd6.onrender.com/admin](https://real-interview-lpd6.onrender.com/admin)  
**Feedback:** [https://real-interview-lpd6.onrender.com/feedback](https://real-interview-lpd6.onrender.com/feedback)

Local development: `http://localhost:5000` (app), `http://localhost:5000/admin` (admin), and `http://localhost:5000/feedback` (feedback).

## 🎯 Vision
Build an Agentic AI application that simulates mock interviews based on a candidate’s resume and job description.  
Initial form: **chat-based app** → later extended with analytics, personalization, and enterprise features.

## Project layout

```
app/real_interview/
├── backend/
│   ├── app_factory.py          # Flask app, blueprint registration, static UI routes
│   ├── server.py               # Entry point — run this to start the server
│   ├── routes/                 # HTTP layer (users, resumes, jobs, interview, avatar, admin, feedback)
│   ├── auth/                   # JWT, cookies, rate limits, admin access
│   ├── services/               # Business logic, MongoDB persistence, SMTP email
│   ├── agents/                 # LLM agents (resume, job, interview panel, candidate avatar)
│   ├── graphs/                 # LangGraph interview workflows
│   ├── nodes/                  # LangGraph node implementations
│   ├── state/                  # Typed state and Pydantic schemas for the pipeline
│   ├── tools/                  # External tools (e.g. Tavily web search)
│   ├── config/                 # Loads params.yaml for interview tuning
│   ├── llm/                    # OpenAI client wrapper
│   └── utils/                  # MongoDB connection, log sanitization
├── frontend/                   # Static UI (index.html, admin.html, feedback.html, *.js)
└── data/                       # Reserved data paths (config, transcripts, etc.)

params.yaml                     # Interview limits, summarizer/feedback thresholds (project root)
```

---

## Modules

---

## 🚀 Phase 1: MVP (3–4 months)
**Objective:** Deliver a secure, working chat-based mock interview app.

### Features
- Resume upload (PDF, DOC, or DOCX) with download of saved files from the user profile.
- Job description input parsing.
- Chat interview simulation with configurable questions-per-interviewer (app default + per-user override).
- Post-interview report (structured feedback + PDF download).
- **Candidate Avatar** — ideal interview answers grounded in the resume (report + live **Discuss with Avatar** chat).
- User profile — interview stats, paused/completed history, resume management, interview settings.
- Website feedback page — visitors email suggestions and bug reports to the site owner.
- Admin dashboard for signups and usage metrics (active accounts only).


**Do not commit `.env`** — it contains secrets. Use `.env_copy` or similar as a template without real keys.

---

## Launch the application

### Prerequisites

- Python 3.11+ (required for legacy `.doc` text extraction)
- MongoDB running and reachable via `MONGODB_URI`
- Valid `OPENAI_API_KEY` and `TAVILY_API_KEY` in `.env`
- `JWT_SECRET_KEY` (32+ random characters) for production, or `ALLOW_INSECURE_JWT_DEV=true` for local dev only

Generate a JWT secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Install dependencies

From the project root:

```bash
python -m venv .venv
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**macOS / Linux**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Start the server (local development)

From the project root with the virtual environment activated:

```bash
python -m app.real_interview.backend.server
```

### Start the server (production)

Use Gunicorn (included in `requirements.txt`):

```bash
gunicorn -c gunicorn.conf.py app.real_interview.backend.wsgi:app
```

The `Procfile` uses the same command for Heroku-style hosts.

---

## Deploy as a public website

The UI is static files served by Flask on the same origin, so no separate frontend deploy or CORS setup is required. LangGraph checkpoints and the question bank use your existing MongoDB cluster.

### Environment variables (production)

Copy from `.env_copy` and set these on your host (never commit real `.env`):

| Variable | Required | Notes |
|----------|----------|-------|
| `MONGODB_URI` | Yes | Same Atlas cluster as local dev |
| `OPENAI_API_KEY` | Yes | |
| `TAVILY_API_KEY` | Yes | Interviewer + Candidate Avatar web search |
| `JWT_SECRET_KEY` | Yes | Local: generate with `secrets.token_hex(32)`. Render: auto-generated via `generateValue: true` in `render.yaml` |
| `ADMIN_EMAILS` | Yes (admin) | Comma-separated signup emails allowed to open `/admin` |
| `FEEDBACK_TO_EMAIL` | Yes (feedback) | Inbox for `/feedback` submissions; defaults to first `ADMIN_EMAILS` if unset |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Yes (feedback) | Outbound mail (e.g. Gmail + [app password](https://support.google.com/accounts/answer/185833)) |
| `SMTP_USE_TLS` | Optional | Default `true` (port `587`) |
| `EMAIL_PROVIDER` | Optional | `smtp` (local) or `resend` (required on Render free — SMTP ports blocked) |
| `RESEND_API_KEY` | Yes (resend) | From **[resend.com/api-keys](https://resend.com/api-keys)** (starts with `re_`) — **not** Render Account → API Keys |
| `RESEND_FROM_EMAIL` | Yes (resend) | e.g. `onboarding@resend.dev` (test sender; must match Resend account setup) |
| `FEEDBACK_FROM_EMAIL` | Optional | Sender address; defaults to `SMTP_USER` or `RESEND_FROM_EMAIL` |
| `FEEDBACK_FROM_NAME` | Optional | Display name in the From header (default `Real Interview`) |
| `COOKIE_SECURE` | Yes (HTTPS) | Set `true` on public HTTPS hosts |
| `MONGODB_*` collections | Yes | See `.env_copy` for names |
| `WEB_CONCURRENCY` | Recommended | `1` on Render free (512 MB); `2` on paid plans |
| `GUNICORN_TIMEOUT` | Recommended | `120` — LLM turns can be slow (avatar report generation can take up to ~60s) |

Do **not** set `ALLOW_INSECURE_JWT_DEV` on a public host.

### Render (free tier)

1. Push the repo to GitHub.
2. In [Render](https://render.com), **New → Blueprint** and point at `render.yaml`.
3. When prompted, enter `MONGODB_URI`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `ADMIN_EMAILS`, and email vars (`EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FEEDBACK_TO_EMAIL`).
4. Deploy. Render auto-generates `JWT_SECRET_KEY` (random 256-bit secret, stored in the dashboard — not in git).
5. Open [https://real-interview-lpd6.onrender.com/](https://real-interview-lpd6.onrender.com/) — the first visit after idle may take ~30–60s while the app wakes up.

**Free tier notes:** service sleeps after ~15 minutes with no traffic; any visit wakes it. You get 750 instance-hours/month. For always-on hosting, change `plan: free` to `plan: starter` in `render.yaml`.

**Email on free tier:** Render [blocks outbound SMTP](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports) on ports 25, 465, and 587 — Gmail SMTP will fail with `Network is unreachable`. Use **`EMAIL_PROVIDER=resend`** with a [Resend](https://resend.com) API key (HTTPS), or upgrade to a paid Render instance to use SMTP. With Resend’s test sender (`onboarding@resend.dev`), set **`FEEDBACK_TO_EMAIL`** to the same address you used to sign up at Resend — website feedback from `/feedback` will deliver there.

### Railway / Heroku / Docker

- **Railway / Heroku:** use the `Procfile` start command; set the same env vars as above.
- **Docker:** `docker build -t real-interview .` then run with `-p 5000:5000 --env-file .env` (use production values and `COOKIE_SECURE=true` over HTTPS).

### MongoDB Atlas checklist

- Allow network access from your host (see **Network access error** below).
- Reuse the same database; collections are created on first use (`interview_question_bank`, `checkpoints`, `rate_limits`, etc.).
- GridFS bucket `resume_pdf_fs` stores uploaded PDFs.

### Network access error (Render / Atlas)

If signup or login shows **Network error**, or Render logs show MongoDB timeout / `ServerSelectionTimeoutError` / **IP not whitelisted**, Atlas is blocking Render.

**Fix (required for Render):**

1. Open [MongoDB Atlas](https://cloud.mongodb.com) → your project → **Network Access** (left sidebar).
2. Click **Add IP Address**.
3. Choose **Allow Access from Anywhere** (`0.0.0.0/0`).  
   Render free tier has no fixed IP, so you must allow all IPs (or the app cannot reach Atlas).
4. Click **Confirm** and wait 1–2 minutes for the rule to apply.
5. In Render → your service → **Logs**, confirm you see `MongoDB connection established` after redeploy or the next request.

**Also verify on Render (Environment tab):**

| Variable | Common mistake |
|----------|----------------|
| `MONGODB_URI` | Extra spaces, missing `mongodb+srv://`, wrong password |
| `OPENAI_API_KEY` / `TAVILY_API_KEY` | Not set or copied with quotes |

Copy `MONGODB_URI` from your local `.env` exactly (no leading/trailing spaces).

**If the UI says "Network error" right after opening the site:** the free tier may still be waking up. Wait 60 seconds and refresh — the HTML loads before the API is ready on cold start.

### Post-deploy smoke test

1. Sign up / log in — you should land on **Your profile** (cookie auth persists).
2. On the profile, set **Interview settings** (optional) and upload a resume; confirm **Download saved resume** works.
3. Click **Start interview** → upload/select resume → save job application → start chat; confirm HR summary and `[I1]` opening message.
4. Pause and resume — summary should carry over.
5. End interview — interview report appears with **Download PDF**; completed row on profile shows a download icon for the report.
6. Profile → **Discuss with Avatar** — ask a practice question; confirm the avatar replies using resume context.
7. Open **Send feedback** (footer link or `/feedback`) — confirm the message arrives in your inbox.

### Open the UI

In your browser:

```
http://localhost:5000
```

Use port **5000** unless you set `PORT` to something else in `.env`.

### Typical flow in the UI

1. **Sign up** or **Log in** — opens **Your profile**
2. **Interview settings** (optional) — question limit per panel member; toggle **ideal answers in reports** (on by default)
3. **Start interview** — upload or select a resume, then save a job application
4. **Live panel chat** — all panelists present from the start (`[I1]`, `[I2]`, …); follow-ups based on your answers
5. **Pause interview** — conversation is summarized and saved; resume later from profile or upload flow
6. **Resume interview** — continue the same session (profile **Resume interview** picks the latest paused session)
7. **End interview** when ready — structured **interview report** with PDF download; **Back to profile** returns to your dashboard
8. **Profile** — view completed/paused counts, download past resumes and summary reports, upload new resumes
9. **Discuss with Avatar** — practice any interview question; ideal avatar answers from your resume (optional web sources)
10. **Send feedback** (footer link) — report bugs or ideas about the site itself
11. **Sign out** clears the browser session

---

## User profile

After login or signup, candidates land on **Your profile** (`/` → profile view when signed in).

### What the profile shows

| Area | Description |
|------|-------------|
| **Actions** | **Start interview**, **Resume interview** (latest paused), **Discuss with Avatar** |
| **Stats** | Clickable counts for completed and paused interviews |
| **Interview tables** | Role, dates, status, message count; completed rows include a download icon for the PDF summary report |
| **Interview settings** | Override `max_questions_per_interviewer` (minimum **4**); toggle **ideal answers in reports** |
| **Resumes** | Upload PDF/DOC/DOCX; list saved files with **Download saved resume** |

### Interview question limit (per candidate)

| Source | Value |
|--------|-------|
| App default | `params.yaml` → `interview.limits.max_questions_per_interviewer` (default **8**) |
| User override | Optional field `max_questions_per_interviewer` on the user document in **`authentications`** |
| Minimum allowed | **4** (enforced on save) |
| When it applies | New interviews snapshot the effective limit at start; in-progress sessions keep the limit from when they started |

Use **Use app default** on the profile to clear a personal override.

### Profile API (JWT required)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/users/profile` | Email, interview counts, interview settings (`default`, `override`, `effective`, `minimum`) |
| `GET /api/users/profile/interviews?status=completed\|paused` | Interview list for profile tables |
| `PUT /api/users/profile/interview-settings` | Body: `{ "max_questions_per_interviewer": 6 }`, `{ "ideal_answer_report_enabled": true }`, or either field alone |
| `GET /api/resumes` | List saved resumes (includes `downloadable` flag) |
| `GET /api/resumes/<resume_id>/download` | Download original uploaded file (GridFS) |
| `GET /api/interview/report?session_id=…` | Structured report JSON (includes ideal answers when enabled) |
| `GET /api/interview/report/download?session_id=…` | PDF download of summary report |
| `GET /api/avatar/discuss/context` | Avatar chat readiness + latest resume metadata |
| `POST /api/avatar/discuss` | Ask the ideal avatar a practice question (see [Candidate Avatar](#candidate-avatar)) |
| `DELETE /api/users` | Delete account (email + password); removes auth, resumes, jobs, in-progress interviews; **completed** interviews retained in DB |

---

## Candidate Avatar

The **Candidate Avatar** is an AI persona built from the candidate’s **parsed resume**. It speaks as the *ideal version* of that candidate: specific, honest, and grounded in real experience (no invented employers or degrees). It uses **Tavily web search** when factual context would improve an answer; sources are listed with titles and URLs.

The avatar is **never** shown during the live mock interview. It appears in two places:

| Mode | Where | When |
|------|--------|------|
| **Ideal answers in report** | Completed interview report (UI + PDF) | First open or download of a report |
| **Discuss with Avatar** | Profile → **Discuss with Avatar** | Any time (requires an uploaded resume) |

### Ideal answers in interview reports

After a completed session, the report can include an **Ideal answers (resume avatar)** section: for each technical Q&A from the interview, the avatar shows what you said and a stronger **ideal answer**.

| Setting | Default | Storage |
|---------|---------|---------|
| `ideal_answer_report_enabled` | **On** (missing field = enabled) | `authentications` collection |
| Applies to | Past and new completed interviews | Generated on first report view/download, cached on the interview record as `ideal_answers_report` |

Uncheck **Include ideal answers in interview reports** on your profile to opt out.

**Example — one Q&A block in the report:**

| Field | Example |
|-------|---------|
| **Asked** | How would you design a REST endpoint to create a payment idempotently? |
| **Your answer** | I'd use a client-supplied idempotency key in a header, store keys in Redis or Mongo with TTL, and return the same response if the key repeats within 24 hours. |
| **Ideal answer** | At Acme Payments I owned idempotent charge APIs. I'd require `Idempotency-Key` on POST, persist `(merchant_id, key) → response` in Mongo with a unique compound index and 24h TTL, return 201 with the same body on replay, and fail with 503 if the store is unavailable so we never double-charge. For scale I'd shard by merchant_id and monitor replay rate. |
| **Web sources** | [Stripe — Idempotent requests](https://stripe.com/docs/api/idempotent_requests) |

**Example — report JSON excerpt** (`GET /api/interview/report?session_id=…`):

```json
{
  "session_id": "…",
  "role_applied_for": "Senior Backend Engineer",
  "feedback": { "overall_assessment": "…", "interview_decision": "hold" },
  "ideal_answers_report": {
    "avatar_summary": "Ideal persona based on five years of Python backend work and payments microservice ownership from the resume.",
    "items": [
      {
        "interviewer": "I1",
        "question": "How would you design a REST endpoint to create a payment idempotently?",
        "candidate_answer": "I'd use a client-supplied idempotency key…",
        "ideal_answer": "At Acme Payments I owned idempotent charge APIs…",
        "web_sources": [
          { "title": "Stripe — Idempotent requests", "url": "https://stripe.com/docs/api/idempotent_requests" }
        ]
      }
    ]
  },
  "ideal_answer_report_enabled": true
}
```

### Discuss with Avatar

From **Your profile**, click **Discuss with Avatar** to open a practice chat. Ask **any** interview question; the avatar replies with the best answer *you* could give, using your **latest uploaded resume**. Conversation history is kept for follow-ups.

**Example chat:**

```
You: How would you handle a production incident where error rates spike after a deploy?

Ideal avatar: In my last role on the payments service, our playbook started with rollback if the deploy
window matched the spike — which it did. I pulled Grafana dashboards for 5xx rate and p99 latency,
joined the incident bridge with on-call and PM, and communicated a 15-minute customer-impact estimate.
Root cause was a connection pool max size regression; we rolled back within 12 minutes, then added a
canary deploy step and pool-saturation alerts. I'd quantify MTTR and affected request volume in the
postmortem.

Web sources:
  • Google SRE — Incident Management
  • https://sre.google/sre-book/managing-incidents/

You: What would you put in the postmortem action items?

Ideal avatar: I'd separate immediate fixes from process changes: (1) patch pool defaults and add an
integration test that asserts pool config, (2) mandatory canary for payment paths, (3) runbook update
with explicit rollback criteria, (4) blameless review within 48 hours with metrics — MTTR, customers
affected, and repeat-incident risk.
```

**Requirements:** at least one resume on your profile. Rate limit: **30 questions per user per hour**.

**Discuss API** (JWT required):

| Endpoint | Method | Body / response |
|----------|--------|-----------------|
| `GET /api/avatar/discuss/context` | GET | `{ "ready": true, "resume_id", "resume_label", "candidate_name", "message" }` |
| `POST /api/avatar/discuss` | POST | Request: `{ "message": "…", "history": [{ "role": "user\|assistant", "content": "…" }], "resume_id?": "…" }` → `{ "ideal_answer", "web_sources": [{ "title", "url" }] }` |

**Example request:**

```bash
curl -X POST http://localhost:5000/api/avatar/discuss \
  -H "Content-Type: application/json" \
  -b "session=YOUR_JWT_COOKIE" \
  -d '{
    "message": "Explain CAP theorem in the context of our payment ledger.",
    "history": []
  }'
```

**Example response:**

```json
{
  "resume_id": "674a…",
  "question": "Explain CAP theorem in the context of our payment ledger.",
  "ideal_answer": "For our ledger I'd prioritize consistency and partition tolerance: every debit/credit must balance atomically within a Mongo transaction or equivalent, even if we sacrifice availability during a network split — we'd rather reject writes briefly than show inconsistent balances. In practice at Acme we used primary reads for balance checks and async replication only for analytics, not customer-facing balance.",
  "web_sources": [
    {
      "title": "MongoDB — Multi-Document Transactions",
      "url": "https://www.mongodb.com/docs/manual/core/transactions/"
    }
  ]
}
```

### Interview settings API (avatar + question limit)

```json
PUT /api/users/profile/interview-settings
{
  "max_questions_per_interviewer": 6,
  "ideal_answer_report_enabled": true
}
```

Set `"ideal_answer_report_enabled": false` to disable ideal answers in reports. Re-enabling clears cached ideal-answer reports so completed sessions regenerate on the next download.

Optional env: `AVATAR_MAX_TOOL_ROUNDS` (default `4`) — max Tavily search rounds per avatar request.

---

## Admin dashboard

Operators can view signups and usage metrics at **`/admin`**.

| Environment | URL |
|-------------|-----|
| Production | [https://real-interview-lpd6.onrender.com/admin](https://real-interview-lpd6.onrender.com/admin) |
| Local | [http://localhost:5000/admin](http://localhost:5000/admin) |

### Access

There is no separate admin account. Access is controlled by **`ADMIN_EMAILS`** in `.env` / Render environment variables:

```env
ADMIN_EMAILS=you@example.com,other@example.com
```

1. Sign up on the main app with an email listed in `ADMIN_EMAILS` (must match exactly).
2. Open `/admin` and log in with that same email and password.
3. Non-admin users see **Access denied** after login.

### What the dashboard shows

**Usage metrics** (filterable by 7 / 30 / 90 days):

| Metric | Description |
|--------|-------------|
| Total users | All registered accounts |
| New today / 7 days / period | Recent signups |
| Interviews total | All interview sessions |
| In progress | `interview_status` = active |
| Paused | Paused interviews |
| Completed | Completed or has feedback |
| Not started | Interview created, no chat messages yet |
| Resumes / job applications | Total uploads and saved applications |

**Tables:**

- **Recent signups** — email, signup time, user ID
- **Recent interviews** — candidate email, role, status, message count, start time (deleted accounts excluded)

### Admin API (JWT + admin email required)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/admin/access` | Check if the signed-in user is an admin |
| `GET /api/admin/dashboard?days=30&limit=50` | Full metrics and tables (JSON) |

---

## Website feedback page

Visitors can send **site feedback** (bugs, feature ideas, usability notes) at **`/feedback`**. This is separate from **post-interview feedback**, which is generated by the AI after you end a mock interview.

| Environment | URL |
|-------------|-----|
| Production | [https://real-interview-lpd6.onrender.com/feedback](https://real-interview-lpd6.onrender.com/feedback) |
| Local | [http://localhost:5000/feedback](http://localhost:5000/feedback) |

The main app footer includes a **Send feedback** link. No account is required, but signed-in users have their email prefilled automatically.

### How it works

1. User picks a **category** (general, bug, feature, usability, other) and writes a message (10–5000 characters).
2. Optional **contact email** — used as `Reply-To` so you can respond directly.
3. `POST /api/feedback` sends the submission to your mailbox via SMTP. Nothing is stored in MongoDB.
4. Rate limit: **5 submissions per IP per hour** (MongoDB-backed, shared across workers).

If SMTP is not configured (and Resend is not set when `EMAIL_PROVIDER=resend`), the page returns **503** and shows a friendly error.

### SMTP configuration

Copy from `.env_copy` and set on your host. Example with Gmail (use an [app password](https://support.google.com/accounts/answer/185833), not your normal login password):

```env
FEEDBACK_TO_EMAIL=you@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_USE_TLS=true
```

`FEEDBACK_TO_EMAIL` is the inbox that receives submissions. If omitted, the first address in `ADMIN_EMAILS` is used.

**What you receive:** subject line includes category (and contact email when provided); body includes the message, optional contact address, signed-in user info (if logged in), and client IP.

**Privacy:** email addresses are masked in server logs (e.g. `a***@example.com`).

### Feedback API

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/feedback` | Optional (cookie JWT) | Submit website feedback; body: `{ "message", "category?", "contact_email?" }` |

---

## Sample interview

The example below is **illustrative** — actual questions and tone depend on your resume, job description, and which interviewer types the router assigns (`positive`, `negative`, `objective`). In the chat UI, interviewers appear as **`[I1]`**, **`[I2]`**, etc.

### Setup (before chat)

| Step | What you provide | What the app does |
|------|------------------|-------------------|
| Resume | PDF for a backend engineer with Python and API experience | Parses skills, roles, and projects |
| Job | Description for *Senior Backend Engineer* (Python, REST, MongoDB) | Extracts role and requirements |
| Start | Click **Start interview** | HR agent writes a first impression; router picks panel size (1 or 2) and interviewer styles |

**HR first impression (shown under “HR summary & panel”) — excerpt:**

> Alex Chen aligns well with the Senior Backend Engineer role: five years of Python services, REST APIs, and MongoDB in production. Resume shows ownership of a payments microservice and on-call rotation. Gaps vs. the posting: limited mention of Kubernetes and no explicit load-testing experience. Recommended focus for the panel: system design, failure handling, and data modeling.

**Panel plan (example for a mid/senior candidate):**

```json
{
  "experience_level": "senior",
  "panel_size": 2,
  "selected_interviewers": ["positive", "objective"],
  "routing_rationale": "Senior profile warrants two interviewers: supportive technical depth plus process-oriented follow-up."
}
```

### Live panel chat (excerpt)

All panelists are in the room from the start. After each answer, a **panel coordinator** picks who should follow up (often 1–2 interviewers per turn). Questions are grounded in what you just said — no manual handoff between interviewers.

**Session limits** (app defaults in `params.yaml` → `interview.limits`; candidates may override question count on their profile — see [User profile](#user-profile)):

| Limit | Default | Behavior |
|-------|---------|----------|
| `max_questions_per_interviewer` | 8 | Each panel member (`I1`, `I2`, …) may ask up to this many technical questions. Profile override minimum **4**; stored on `authentications`. |
| `max_candidate_qa_turns` | 2 | After all panelists reach their limit, the panel invites your questions; up to 2 Q&A rounds, then the session auto-ends |

If you reply that you have **no questions** when invited, the interview ends immediately and the interview report is generated. You can still click **End interview** early at any time.

When the session ends, the **interview report** appears in the UI with a **Download PDF** button. From your profile, open **Interviews completed** and use the download icon in the **Report** column for past sessions.

**Report API** (JWT, completed sessions only):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/interview/report?session_id=…` | Structured report JSON |
| `GET /api/interview/report/download?session_id=…` | PDF download |

```
[I1]: Hi Alex, I'm on the engineering panel. I've reviewed your background on the payments service —
     great work. Let's start simple: how would you design a REST endpoint to create a payment idempotently?

You: I'd use a client-supplied idempotency key in a header, store keys in Redis or Mongo with TTL,
     and return the same response if the key repeats within 24 hours.

[I1]: Good. What happens if Mongo is down during the idempotency check?

You: Fail fast with 503, don't double-charge; retry from the client with the same key.

[I1]: Makes sense. Can you walk through how you'd index the idempotency collection?

You: Unique index on (user_id, idempotency_key), maybe shard by user_id at scale.

[I2]: Switching to process — describe how you handled a production incident on that service.

You: We had elevated 5xx after a deploy; rolled back, traced to a connection pool misconfiguration,
     added alerts on pool saturation and a runbook step for pool sizing.

[I2]: Who was in the loop, and what did you change in the release process afterward?

You: On-call, PM for customer comms, postmortem within 48h; added staging load test and canary deploy.
```

### Pause and resume

After a few more exchanges, the candidate clicks **Pause interview**. The summarizer runs on the conversation so far and appends to `interview_summary`, for example:

> **Saved summary (excerpt):** Candidate explained idempotent payments with header keys and unique indexes; discussed 503 behavior when dependencies fail. Second interviewer covered a production rollback, stakeholder communication, and post-incident process improvements (canary, load test).

Status becomes **paused**; chat input is disabled until **Resume interview**. On resume, that summary is injected as context for the next panel follow-ups so interviewers do not “forget” earlier answers.

If you sign out or open the app in a new browser session, logging back in automatically restores a **paused or in-progress** interview (or use **Continue interview** on the upload/job screens).

### End interview — sample feedback

After **End interview**, the feedback agent may produce structured output like:

```json
{
  "overall_assessment": "Strong technical communication and relevant backend experience; process answers were concrete.",
  "strengths": [
    "Clear idempotency and indexing explanation",
    "Honest failure-mode thinking (503, no double-charge)",
    "Structured incident narrative with follow-up process changes"
  ],
  "areas_to_improve": [
    "Expand on Kubernetes and observability if targeting this exact posting",
    "Quantify impact of the incident (duration, customers affected)"
  ],
  "recommendation": "Continue practicing system design under time pressure and deepen cloud-native tooling stories.",
  "interview_decision": "hold",
  "detailed_feedback": "You demonstrated solid API design instincts and mature incident handling. To move from hold to selected for a senior backend role, add more depth on scaling, SLOs, and platform operations aligned with the job description."
}
```

This feedback appears in the UI as an **interview report** with a **Download PDF** button; download past reports from **Your profile** → **Interviews completed**. Full message history and summaries remain in MongoDB for that session.

### Ideal answers in the report (avatar)

When **ideal answers in reports** is enabled (default), opening or downloading the report for the session above adds an **Ideal answers** section. Example for `[I1]`’s idempotency question:

**Your answer (excerpt):**  
*Unique index on (user_id, idempotency_key), maybe shard by user_id at scale.*

**Ideal avatar answer (excerpt):**  
*At Acme I implemented idempotent POST /charges with mandatory `Idempotency-Key`, a unique Mongo index on `(merchant_id, key)`, 24h TTL, 503 on store failure to avoid double-charge, and metrics on replay rate. I’d cite our postmortem where replay storms after a partial outage taught us to cap key length and log duplicate client retries.*

See [Candidate Avatar](#candidate-avatar) for the full JSON shape, **Discuss with Avatar** chat, and API details.

---

## Dependencies

See `requirements.txt`: Flask, PyMongo, bcrypt, pypdf, python-docx, legacy-doc, python-dotenv, PyYAML, langchain-openai, langgraph, langchain-core, tavily-python, fpdf2 (interview report PDFs).
