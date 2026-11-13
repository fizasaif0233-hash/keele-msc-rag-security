# System architecture

The browser talks to two services.

1. Supabase Auth issues and refreshes the session. The frontend holds only the public Supabase URL and anon key.
2. The FastAPI service receives the access token, verifies it, loads the caller's role from `profiles`, and performs RAG, experiments, and logging.

The frontend does not send a role, and the API does not trust a role claim inside the token. `identity_from_claims` returns the subject and email only. A missing profile is created with the role `employee`.

```text
Browser (Next.js)
  |-- Supabase Auth (login, registration, password reset)
  |-- FastAPI /api/v1
        |-- authorisation and security controls
        |-- document extraction, chunking, embeddings
        |-- pgvector retrieval
        |-- OpenAI-compatible chat and embedding APIs
        |-- experiment runner and metric calculation
        |-- PostgreSQL (Supabase)
```

## Request path for a question

1. The chat request is authenticated.
2. Employees are forced onto the secured configuration. Researchers and administrators may select baseline. The experiment runner may still execute baseline as an employee actor, because that is the controlled comparison and it is not exposed as an employee self-service option.
3. The question is validated. Keyword patterns are recorded for the secured configuration. They do not, by themselves, reject the question.
4. The server loads documents the actor may read and the documents that are ready.
5. `resolve_document_scope` builds an explicit document list. The secured list is the intersection of the request and the authorised set. The baseline list is not permission-filtered. An empty secured list stays empty.
6. The query is embedded and `match_document_chunks` searches only that list. The SQL function returns nothing when the list is null.
7. Prompt construction differs by configuration. See `docs/security-controls.md`.
8. The model response is checked for synthetic markers. Only the secured configuration redacts markers the actor is not allowed to see.
9. The answer, latency, sources, and warnings are stored with the chat. Experiment trials store the scoring decision as well.

## Process model

The API is intended to run as one Uvicorn worker. Experiment execution uses a background thread in that process and a Postgres advisory lock so two runs are not started together. A restart marks an in-progress experiment as failed and keeps trial rows already committed. That failure is an interruption, not a security result.

## Configuration source of truth

`app/security/configurations.py` records which controls each configuration enables. The settings page exposes non-secret retrieval and model-name settings. Provider credentials remain environment variables.
