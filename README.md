# Real Interview

Flask application for user accounts, resume upload and parsing, and job application capture. The web UI is served from the same server as the REST APIs.

## Project layout

```
app/real_interview/
├── backend/
│   ├── app_factory.py      # Flask app and blueprint registration
│   ├── server.py           # Entry point (run this to start the server)
│   ├── routes/             # HTTP API blueprints
│   ├── services/           # Business logic and MongoDB access
│   ├── agents/             # LLM structured-extraction agents
│   ├── llm/                # OpenAI model configuration
│   └── utils/              # Shared helpers (e.g. MongoDB connection)
└── frontend/               # Static UI (HTML, CSS, JavaScript)
```

## Modules

### Backend core

| Module | Purpose |
|--------|---------|
| `app_factory.py` | Creates the Flask app, registers API blueprints, serves the frontend at `/`, `/styles.css`, `/app.js`. |
| `server.py` | Starts the development server (`HOST`, `PORT` from environment). |
| `utils/mongodb.py` | Connects to MongoDB using `MONGODB_URI`. |

### Routes (`backend/routes/`)

Thin HTTP layer: validates input, calls services, returns JSON.

| File | Prefix |
|------|--------|
| `user_maintenance_routes.py` | `/api` |
| `resume_routes.py` | `/api` |
| `job_application_routes.py` | `/api` |

### Services (`backend/services/`)

| Module | Purpose |
|--------|---------|
| `user_maintenance.py` | Sign up, login, password change, delete user. Stores users in the `authentications` collection (bcrypt passwords). |
| `pdfreader.py` | `resume_reader` class: PDF validation, GridFS storage, text extraction, resume CRUD per user. |
| `job_application.py` | Saves job applications: fetches job URLs (when possible), normalizes descriptions, writes to `job_application` collection. |

### Agents (`backend/agents/`)

| Module | Purpose |
|--------|---------|
| `resume_parse_agent.py` | Uses OpenAI structured output to turn resume text into `parsed_data` (name, experience, skills, etc.). |
| `job_application_agent.py` | Extracts `job_role` and agent-readable `job_description` from posting text or scraped HTML. |

### LLM (`backend/llm/`)

| Module | Purpose |
|--------|---------|
| `openaillm.py` | Loads `OPENAI_API_KEY` and returns a `ChatOpenAI` instance (`gpt-4o-mini`). Used by both agents. |

### Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `index.html` | Account, resume upload/fetch, and job application views. |
| `app.js` | UI flow, session storage (`user_id`, email, selected `resume_id`), API calls. |
| `styles.css` | Layout and styling. |

### Reserved (not used yet)

`backend/nodes/`, `backend/state/`, `backend/tools/` — placeholders for a future LangGraph-style pipeline.

---

## APIs

All JSON APIs are under `/api`. The UI uses these endpoints; you can also call them directly (e.g. with Postman).

### Users — `user_maintenance_routes.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/users` | Sign up. Body: `email`, `password`, `confirm_password`. Returns `user_id`, `email`. |
| `POST` | `/api/users/login` | Log in. Body: `email`, `password`. Returns `user_id`, `email`. |
| `PUT` | `/api/users/password` | Change password. Body: `email`, `new_password`, `confirm_new_password`. |
| `DELETE` | `/api/users` | Delete account. Body: `email`, `password`. |

### Resumes — `resume_routes.py`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/resumes?userid={id}` | List resumes for a user (newest first). Returns `resumes[]` with `resume_id`, `uploaded_ts`, `label`. |
| `GET` | `/api/resumes/{resume_id}?userid={id}` | Get one resume including `parsed_data`. |
| `POST` | `/api/resumes` | Upload a PDF. Multipart form: `userid`, file field `resume` (or `file` / `pdf`). Returns parsed resume metadata (no `raw_text` in response). |

### Job applications — `job_application_routes.py`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/job-applications` | Save a job application. JSON body: |

**Link mode**

```json
{
  "customer_id": "<user ObjectId>",
  "input_mode": "link",
  "application_link": "https://..."
}
```

**Description mode** (when the site blocks fetching, or user pastes text)

```json
{
  "customer_id": "<user ObjectId>",
  "input_mode": "description",
  "job_description_text": "..."
}
```

Response includes `job_role`, `application_link` (`"NA"` in description mode), `job_description`, `job_application_ts`.

On blocked URLs: `422` with `error_code: "job_url_blocked"` and `suggest_input_mode: "description"`.

### UI (static)

| Method | Path |
|--------|------|
| `GET` | `/` |
| `GET` | `/styles.css` |
| `GET` | `/app.js` |

---

## MongoDB collections

| Collection | Env variable (default) | Contents |
|----------|------------------------|----------|
| Users | `MONGODB_COLLECTION_USERS` (`authentications`) | Email, password hash |
| Resumes | `MONGODB_COLLECTION_RESUMES` | `userid`, `parsed_data`, `raw_text`, GridFS file ref, `uploaded_ts` |
| Job applications | `MONGODB_COLLECTION_JOB_APPLICATIONS` (`job_application`) | `customer_id`, `job_role`, `application_link`, `job_description`, `job_application_ts` |

Resume PDF binaries are stored in GridFS (`MONGODB_GRIDFS_RESUME_BUCKET`, default `resume_pdf_fs`).

---

## Environment variables

Create a `.env` file in the project root:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=real_interview
MONGODB_COLLECTION_USERS=authentications
MONGODB_COLLECTION_RESUMES=resumes
MONGODB_COLLECTION_JOB_APPLICATIONS=job_application
MONGODB_GRIDFS_RESUME_BUCKET=resume_pdf_fs

OPENAI_API_KEY=your-key-here

# Optional
PORT=5000
HOST=0.0.0.0
RESUME_PARSE_MAX_CHARS=14000
JOB_APPLICATION_MAX_CHARS=16000
```

---

## Launch the application

### 1. Prerequisites

- Python 3.10+
- MongoDB running and reachable via `MONGODB_URI`
- OpenAI API key

### 2. Install dependencies

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

### 3. Configure environment

Add `.env` in the project root (see [Environment variables](#environment-variables)).

### 4. Start the server

From the project root with the virtual environment activated:

```bash
python -m app.real_interview.backend.server
```

### 5. Open the app

In a browser:

```
http://localhost:5000
```

### 6. Typical flow in the UI

1. **Sign up** or **Log in**
2. **Upload resume** (PDF) or **Fetch resume** to reuse an existing one
3. **Continue to job application** — provide a job link or paste a job description
4. **Sign out** clears the session (including the selected resume)

---

## Dependencies

See `requirements.txt`: Flask, PyMongo, bcrypt, pypdf, langchain-openai, python-dotenv.
