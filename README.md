# RAG security evaluation platform

Research application for comparing a baseline RAG configuration with a secured configuration on a fictional document corpus. Experimental numbers are calculated from stored trials. The repository does not contain pre-written findings.

The design, controls, metrics, and setup steps are in [`docs`](docs). Start with [installation](docs/installation-guide.md) and [limitations](docs/limitations.md).

## Layout

| Path | Contents |
| --- | --- |
| `frontend` | Next.js interface |
| `backend` | FastAPI application, security controls, RAG pipeline, experiment runner, and Pytest suite |
| `supabase/migrations/0001_init.sql` | PostgreSQL schema, pgvector search, and row-level security |
| `docs` | Research and operator documentation |

## Run

Backend, from `backend`, after the virtual environment and `.env` file exist:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend, from `frontend`:

```powershell
npm run dev
```

The interface is `http://localhost:3000`. API health is `http://127.0.0.1:8000/api/v1/health`.

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python -m pytest
```

## Experiments

From `backend`, after seeding:

```powershell
.\.venv\Scripts\python scripts\run_experiment.py --email researcher.synthetic@keele-rag.example --name "Paired run" --configurations baseline secured --repetitions 1
```

The same action is available on the Experiments page. Export CSV or JSON from Evaluation.

## Credentials that must be supplied locally

- Supabase database URL, project URL, anon key, and service-role key.
- Supabase JWT secret when the project uses HS256.
- An OpenAI-compatible model key.
- A seed password chosen by the operator.

None of these values are stored in the source. There is no default administrator password. Register an account and run `backend/scripts/promote_admin.py`.
