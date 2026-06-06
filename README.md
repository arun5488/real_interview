# Real Interview

Flask application that guides a candidate from account setup through resume upload, job application, and an AI-driven mock interview. The web UI is served from the same server as the backend.

## 🎯 Vision
Build an Agentic AI application that simulates mock interviews based on a candidate’s resume and job description.  
Initial form: **chat-based app** → later extended with analytics, personalization, and enterprise features.

## Project layout

```
app/real_interview/
├── backend/
│   ├── app_factory.py          # Flask app, blueprint registration, static UI routes
│   ├── server.py               # Entry point — run this to start the server
│   ├── routes/                 # HTTP layer (users, resumes, jobs, interview)
│   ├── services/               # Business logic and MongoDB persistence
│   ├── agents/                 # LLM agents (resume, job, interview panel)
│   ├── graphs/                 # LangGraph interview workflows
│   ├── nodes/                  # LangGraph node implementations
│   ├── state/                  # Typed state and Pydantic schemas for the pipeline
│   ├── tools/                  # External tools (e.g. Tavily web search)
│   ├── config/                 # Loads params.yaml for interview tuning
│   ├── llm/                    # OpenAI client wrapper
│   └── utils/                  # MongoDB connection and shared helpers
├── frontend/                   # Static UI (HTML, CSS, JavaScript)
└── data/                       # Reserved data paths (config, transcripts, etc.)

params.yaml                     # Interview summarizer/feedback thresholds (project root)
```

---

## Modules

---

## 🚀 Phase 1: MVP (3–4 months)
**Objective:** Deliver a secure, working chat-based mock interview app.

### Features
- Resume upload (PDF/DOC).
- Job description input parsing.
- Chat interview simulation.
- Feedback summary (strengths, weaknesses, improvements).


**Do not commit `.env`** — it contains secrets. Use `.env_copy` or similar as a template without real keys.

---

## Launch the application

### Prerequisites

- Python 3.10+
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
| `JWT_SECRET_KEY` | Yes | 32+ random chars; generate with `secrets.token_hex(32)` |
| `COOKIE_SECURE` | Yes (HTTPS) | Set `true` on public HTTPS hosts |
| `MONGODB_*` collections | Yes | See `.env_copy` for names |
| `WEB_CONCURRENCY` | Recommended | `2` for starter plans |
| `GUNICORN_TIMEOUT` | Recommended | `120` — LLM turns can be slow |

Do **not** set `ALLOW_INSECURE_JWT_DEV` on a public host.

### Render (recommended)

1. Push the repo to GitHub.
2. In [Render](https://render.com), **New → Blueprint** and point at `render.yaml`, or **New → Web Service** manually.
3. Set secret env vars in the dashboard: `MONGODB_URI`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `JWT_SECRET_KEY`.
4. Deploy. Render sets `PORT` automatically; `COOKIE_SECURE=true` is in the blueprint.
5. Open the service URL — sign up and run a test interview.

### Railway / Heroku / Docker

- **Railway / Heroku:** use the `Procfile` start command; set the same env vars as above.
- **Docker:** `docker build -t real-interview .` then run with `-p 5000:5000 --env-file .env` (use production values and `COOKIE_SECURE=true` over HTTPS).

### MongoDB Atlas checklist

- Allow network access from your host (or `0.0.0.0/0` for managed PaaS).
- Reuse the same database; collections are created on first use (`interview_question_bank`, `checkpoints`, `rate_limits`, etc.).
- GridFS bucket `resume_pdf_fs` stores uploaded PDFs.

### Post-deploy smoke test

1. Sign up / log in (cookie auth should persist).
2. Upload a resume and save a job application.
3. Start interview — confirm HR summary and `[I1]` opening message.
4. Pause and resume — summary should carry over.
5. End interview — feedback saved; sign out clears the session.

### Open the UI

In your browser:

```
http://localhost:5000
```

Use port **5000** unless you set `PORT` to something else in `.env`.

### Typical flow in the UI

1. **Sign up** or **Log in**
2. **Upload resume** (PDF) or **Fetch resume** to select an existing one
3. **Continue to job application** — job link or pasted description, then save
4. **Start interview** — HR summary and panel load; chat with interviewers (`[I1]`, `[I2]`, …)
5. **Pause interview** — conversation is summarized and saved; resume later with that context
6. **Resume interview** — continue the same session
7. **Next interviewer** / **End interview** when appropriate; feedback appears after completion
8. **Sign out** clears the browser session

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

### Chat transcript (excerpt)

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

Status becomes **paused**; chat input is disabled until **Resume interview**. On resume, that summary is injected as context for the next interviewer turns so the panel does not “forget” earlier answers.

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

See `requirements.txt`: Flask, PyMongo, bcrypt, pypdf, python-dotenv, PyYAML, langchain-openai, langgraph, langchain-core, tavily-python.
