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
│   ├── routes/                 # HTTP layer (users, resumes, jobs, interview, admin, feedback)
│   ├── auth/                   # JWT, cookies, rate limits, admin access
│   ├── services/               # Business logic, MongoDB persistence, SMTP email
│   ├── agents/                 # LLM agents (resume, job, interview panel)
│   ├── graphs/                 # LangGraph interview workflows
│   ├── nodes/                  # LangGraph node implementations
│   ├── state/                  # Typed state and Pydantic schemas for the pipeline
│   ├── tools/                  # External tools (e.g. Tavily web search)
│   ├── config/                 # Loads params.yaml for interview tuning
│   ├── llm/                    # OpenAI client wrapper
│   └── utils/                  # MongoDB connection, log sanitization
├── frontend/                   # Static UI (index.html, admin.html, feedback.html, *.js)
└── data/                       # Reserved data paths (config, transcripts, etc.)

params.yaml                     # Interview summarizer/feedback thresholds (project root)
```

---

## Modules

---

## 🚀 Phase 1: MVP (3–4 months)
**Objective:** Deliver a secure, working chat-based mock interview app.

### Features
- Resume upload (PDF, DOC, or DOCX).
- Job description input parsing.
- Chat interview simulation.
- Feedback summary (strengths, weaknesses, improvements).
- Website feedback page — visitors email suggestions and bug reports to the site owner.
- Admin dashboard for signups and usage metrics.


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
| `TAVILY_API_KEY` | Yes | Interviewer web search |
| `JWT_SECRET_KEY` | Yes | Local: generate with `secrets.token_hex(32)`. Render: auto-generated via `generateValue: true` in `render.yaml` |
| `ADMIN_EMAILS` | Yes (admin) | Comma-separated signup emails allowed to open `/admin` |
| `FEEDBACK_TO_EMAIL` | Yes (feedback) | Inbox for `/feedback` submissions; defaults to first `ADMIN_EMAILS` if unset |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Yes (feedback) | Outbound mail (e.g. Gmail + [app password](https://support.google.com/accounts/answer/185833)) |
| `SMTP_USE_TLS` | Optional | Default `true` (port `587`) |
| `SEND_INTERVIEW_FEEDBACK_EMAIL` | Optional | Default `true` — email post-interview feedback when the candidate opts in |
| `EMAIL_PROVIDER` | Optional | `smtp` (local) or `resend` (required on Render free — SMTP ports blocked) |
| `RESEND_API_KEY` | Yes (resend) | From [resend.com](https://resend.com) — used when `EMAIL_PROVIDER=resend` |
| `RESEND_FROM_EMAIL` | Yes (resend) | Verified sender, e.g. `Real Interview <onboarding@resend.dev>` for testing |
| `FEEDBACK_FROM_EMAIL` | Optional | Sender address; defaults to `SMTP_USER` or `RESEND_FROM_EMAIL` |
| `FEEDBACK_FROM_NAME` | Optional | Display name in the From header (default `Real Interview`) |
| `COOKIE_SECURE` | Yes (HTTPS) | Set `true` on public HTTPS hosts |
| `MONGODB_*` collections | Yes | See `.env_copy` for names |
| `WEB_CONCURRENCY` | Recommended | `1` on Render free (512 MB); `2` on paid plans |
| `GUNICORN_TIMEOUT` | Recommended | `120` — LLM turns can be slow |

Do **not** set `ALLOW_INSECURE_JWT_DEV` on a public host.

### Render (free tier)

1. Push the repo to GitHub.
2. In [Render](https://render.com), **New → Blueprint** and point at `render.yaml`.
3. When prompted, enter `MONGODB_URI`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `ADMIN_EMAILS`, and SMTP vars for feedback email (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `FEEDBACK_TO_EMAIL`).
4. Deploy. Render auto-generates `JWT_SECRET_KEY` (random 256-bit secret, stored in the dashboard — not in git).
5. Open [https://real-interview-lpd6.onrender.com/](https://real-interview-lpd6.onrender.com/) — the first visit after idle may take ~30–60s while the app wakes up.

**Free tier notes:** service sleeps after ~15 minutes with no traffic; any visit wakes it. You get 750 instance-hours/month. For always-on hosting, change `plan: free` to `plan: starter` in `render.yaml`.

**Email on free tier:** Render [blocks outbound SMTP](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports) on ports 25, 465, and 587 — Gmail SMTP will fail with `Network is unreachable`. Use **`EMAIL_PROVIDER=resend`** with a [Resend](https://resend.com) API key (HTTPS), or upgrade to a paid Render instance to use SMTP.

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

1. Sign up / log in (cookie auth should persist).
2. Upload a resume and save a job application.
3. Start interview — confirm HR summary and `[I1]` opening message.
4. Pause and resume — summary should carry over.
5. End interview — post-interview feedback saved; sign out clears the session.
6. Open **Send feedback** (footer link or `/feedback`) — confirm the message arrives in your inbox.

### Open the UI

In your browser:

```
http://localhost:5000
```

Use port **5000** unless you set `PORT` to something else in `.env`.

### Typical flow in the UI

1. **Sign up** or **Log in**
2. **Upload resume** (PDF, DOC, or DOCX) or **Fetch resume** to select an existing one
3. **Continue to job application** — job link or pasted description, then save
4. **Start interview** — HR summary and panel load; all panelists are present in a live session (`[I1]`, `[I2]`, …)
5. **Pause interview** — conversation is summarized and saved; resume later with that context
6. **Resume interview** — continue the same session
7. **Answer in chat** — the panel picks follow-up questions from your replies (one or two interviewers may respond per turn)
8. **End interview** when ready — post-interview feedback appears after completion
9. **Send feedback** (footer link) — report bugs or ideas about the site itself
10. **Sign out** clears the browser session

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
- **Recent interviews** — candidate email, role, status, message count, start time

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

If SMTP is not configured, the page returns **503** and shows a friendly error.

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

**Session limits** (configurable in `params.yaml` → `interview.limits`):

| Limit | Default | Behavior |
|-------|---------|----------|
| `max_questions_per_interviewer` | 8 | Each panel member (`I1`, `I2`, …) may ask up to 8 technical questions |
| `max_candidate_qa_turns` | 2 | After all panelists reach their limit, the panel invites your questions; up to 2 Q&A rounds, then the session auto-ends |

If you reply that you have **no questions** when invited, the interview ends immediately and post-interview feedback is generated. You can still click **End interview** early at any time.

**Email feedback:** On the interview chat screen, check **Email feedback to my account address**. When the session ends (manually or automatically), structured feedback is emailed to your signup address if SMTP is configured and `SEND_INTERVIEW_FEEDBACK_EMAIL=true`.

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

This feedback appears in the UI under **Post-interview feedback**; the full message history and summaries remain in MongoDB for that session.

---

## Dependencies

See `requirements.txt`: Flask, PyMongo, bcrypt, pypdf, python-docx, legacy-doc, python-dotenv, PyYAML, langchain-openai, langgraph, langchain-core, tavily-python.
