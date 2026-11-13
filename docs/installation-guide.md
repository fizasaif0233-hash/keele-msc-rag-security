# Installation guide

The commands below assume Windows PowerShell and the repository root `Project-Keele MSC`. Python 3.11 and Node.js 20 were used during development.

## 1. Supabase project

1. Create a Supabase project.
2. In the SQL editor, enable the `vector` extension if it is not already available. The Database extensions page can do this.
3. Run `supabase/migrations/0001_init.sql`.
4. If the editor reports that the type `vector` does not exist, enable the extension and run the script again. On some projects the extension lives in the `extensions` schema and that schema must be on the SQL `search_path`.
5. Under Authentication, decide whether new users must confirm email. For a local study, disabling confirmation avoids a blocked first login. For a hosted study, leave confirmation on and use the reset-password redirect below.
6. Add `http://localhost:3000/reset-password` to the authentication redirect URLs.

Copy the project URL, anon key, service-role key, and database URI. Prefer the direct database connection on port 5432. The transaction pooler can interfere with the advisory lock used by the experiment runner.

## 2. Backend environment

```powershell
cd backend
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Edit `backend/.env`:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Supabase Postgres URI. The application accepts `postgresql://` and uses psycopg. |
| `SUPABASE_URL` | Project URL, used to verify asymmetric tokens and to seed users. |
| `SUPABASE_JWT_SECRET` | Required for HS256 session tokens. Leave empty only when the project signs tokens with the JWKS keys. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server and seed script only. Never place this in the frontend. |
| `LLM_API_KEY` | OpenAI-compatible key. |
| `LLM_BASE_URL` | Defaults to `https://api.openai.com/v1`. |
| `LLM_MODEL` | Chat model name. |
| `EMBEDDING_MODEL` | Must return 1536-dimensional vectors unless the migration is changed. |
| `EMBEDDING_DIMENSIONS` | Keep at 1536 to match the schema. |
| `CORS_ORIGINS` | Frontend origin, normally `http://localhost:3000`. |
| `SEED_USER_PASSWORD` | At least 12 characters. Used only by the seed script. It is not a default account password in the source. |

## 3. First administrator

There is no built-in administrator password.

1. Start the frontend and register your own account.
2. If email confirmation is on, confirm the account.
3. Promote it:

```powershell
cd backend
.\.venv\Scripts\python scripts\promote_admin.py --email you@example.com
```

The account must already have a profile. The script only changes the role.

## 4. Synthetic data

Set `SEED_USER_PASSWORD`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`, then:

```powershell
cd backend
.\.venv\Scripts\python scripts\seed.py
```

The script creates four fictional accounts if they are absent, assigns their roles, loads the text corpus, and upserts the official test cases. Run it again after adding the model key, or pass `--refresh`, to embed documents that were left `pending`.

Synthetic addresses:

- `admin.synthetic@keele-rag.example`
- `employee.synthetic@keele-rag.example`
- `employee2.synthetic@keele-rag.example`
- `researcher.synthetic@keele-rag.example`

They all use the password you supplied in the environment. Do not commit that password.

## 5. Frontend environment

```powershell
cd frontend
copy .env.example .env.local
npm install
```

Set `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_API_URL`. The anon key is the public Supabase key. Do not put the service-role key or the model key in `.env.local`.

## 6. Run the application

In one terminal:

```powershell
cd backend
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use one worker. In another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`. The health check is `http://127.0.0.1:8000/api/v1/health`. Interactive API documentation is `http://127.0.0.1:8000/docs`.

## 7. Tests and checks

From `backend`, with the virtual environment active:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check app tests scripts
.\.venv\Scripts\python -m mypy app scripts
```

From `frontend`:

```powershell
npm run typecheck
npm run lint
npm run build
```

The Pytest suite does not need a database. A live experiment does.
