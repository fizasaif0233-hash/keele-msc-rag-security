# Project audit

Audit date: 13 November 2026.

This audit records what is present in the repository and what was observed in the running application. It does not treat the project brief as evidence that a feature exists. No application logic was changed while this file was written.

## Confirmed technologies

| Area | What the repository uses |
| --- | --- |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, Recharts. Package name `rag-security-evaluation`. |
| Frontend authentication | Supabase Auth through `@supabase/ssr` and `@supabase/supabase-js`. `frontend/middleware.ts` redirects an unsigned visitor away from application pages. |
| Backend | FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2, psycopg. |
| Database | Supabase PostgreSQL. Schema in `supabase/migrations/0001_init.sql` and `supabase/migrations/0002_hr_access_level.sql`. Vector column `vector(1536)` with an HNSW cosine index. |
| Retrieval | SQL function `match_document_chunks`. Similarity is `1 - (embedding <=> query)`. A null or empty allow-list returns no rows. |
| Model client | An OpenAI-compatible HTTP client in `backend/app/rag/llm.py`. The runtime settings observed on 13 November 2026 were chat model `gemini-3.5-flash-lite`, embedding model `gemini-embedding-001`, 1536 dimensions, temperature `0.0`, top-k `8`, similarity threshold `-1.0`. |
| Document files | Local directory configured by `STORAGE_DIR`, not Supabase Storage. PDF text is extracted with `pypdf`. TXT is read directly. |
| Tests | Pytest, Ruff, and Mypy are declared in `backend/requirements.txt`. There is no frontend test runner and no Playwright suite. |
| Interface charts | Recharts on the analytics page. Null rates are not drawn as zero. |

The workspace used to run the application was Python 3.11 and Node.js 20. There is no root `README`. Project documentation is in `docs/`.

## Repository layout

- `frontend/` — Next.js application.
- `backend/app/` — API, authentication, RAG pipeline, security controls, evaluation, and seed catalogue.
- `backend/tests/` — Pytest modules.
- `backend/scripts/` — `seed.py`, `promote_admin.py`, `run_experiment.py`.
- `backend/app/seed/files/` — eight synthetic text documents.
- `supabase/migrations/` — schema and row-level security.
- `docs/` — research question, architecture, methodology, metrics, test cases, security controls, limitations, installation, and user guide.
- `dissertation/` — this audit. No dissertation chapter existed before this file.

The working directory is not a Git repository. There is no commit history, tag, or branch record to use as a project timeline.

## Implemented features

### Accounts and server-side authentication

- Registration, login, and password-reset pages exist: `frontend/app/register/page.tsx`, `frontend/app/login/page.tsx`, `frontend/app/reset-password/page.tsx`.
- The API requires a bearer token on every route except the health check. `backend/app/deps.py` verifies the token and loads `profiles`. A missing profile is created with role `employee`.
- JWT verification accepts HS256 when `SUPABASE_JWT_SECRET` is set, and RS256 or ES256 through the project JWKS endpoint (`backend/app/auth/jwt.py`). The role is not taken from token claims.
- New Supabase users receive an employee profile from `handle_new_user()` in the migration. The trigger updates email on conflict and does not copy a role from user metadata.
- Failed authentication writes `authentication_failure` to `security_logs`.

### Roles and document authorisation

Roles stored in `profiles.role` are `admin`, `employee`, and `researcher`. There is no HR user role.

Document access levels are `public`, `employee`, `hr`, `confidential`, and `admin`. `can_read_document` in `backend/app/auth/permissions.py` allows a document when the caller is an administrator, the owner, or the holder of an explicit grant. Otherwise `public` is readable by any authenticated caller, and `employee` is readable by employee, researcher, and administrator. `hr`, `confidential`, and `admin` are denied unless one of the earlier conditions applies.

Only an administrator can change an access level or a grant. A non-administrator upload may be labelled only `public` or `employee`. Employees cannot upload unless `allow_employee_upload` is enabled. The observed runtime value was false. Employees cannot select baseline chat; the experiment runner may still execute baseline with `experiment_execution=True`.

Hidden documents are returned as not found by the document API, and a blocked read writes `blocked_document_access`.

### Documents, processing, and RAG

- Upload accepts PDF and TXT, checks the extension against a small content-type set, and enforces a size limit. The stored name is a UUID plus the extension.
- Text is chunked with the configured size and overlap. The observed defaults are 800 and 120. Chunk settings are stored on an experiment for the record. A trial does not rebuild the index.
- Embeddings are written to `document_chunks`. Retrieval passes an explicit document-id list.
- Chat and experiments both call `answer_question` in `backend/app/rag/pipeline.py`.
- The baseline configuration puts retrieved text in the system message and does not apply permission filtering, prompt separation, marker redaction, or RAG security-decision logs.
- The secured configuration intersects the request with documents the caller may read, places retrieved text in the user message between untrusted-reference markers, uses a fixed system prompt, applies a stricter input-length limit, redacts unauthorised synthetic markers in the answer and in source excerpts, and writes selected security decisions.
- Secured redaction ignores letter case and the zero-width characters U+200B, U+200C, U+200D, and U+FEFF. It does not treat a marker split by an ordinary space as a match. Baseline answers and excerpts are not redacted.
- Suspicious phrases are labelled. They do not by themselves reject a question.
- Both configurations reject an empty question and enforce an absolute ceiling of 20,000 characters. The observed secured limit is 4,000 characters and the observed baseline limit is 12,000.
- A process-local chat rate limit applies to both configurations.
- Security-log metadata removes values whose keys match password, token, secret, authorisation, or API-key patterns, and it truncates long strings. It does not scan ordinary values for secrets.

### Research workflow

The interface includes dashboard, documents, chat, research cases, experiments, analytics, logs, and settings. Research pages are limited to administrator and researcher roles in the API. Settings can be read by those roles and changed only by an administrator.

The official dataset is “Synthetic RAG security dataset v1”. It contains 15 cases: four benign, three direct prompt injection, two indirect prompt injection, four unauthorised disclosure, and two input validation. Case definitions are in `backend/app/seed/catalog.py` and `docs/test-cases.md`.

A paired experiment stores one comparison group, one dataset, one repetition count, and one parameter snapshot on both the baseline row and the secured row. The snapshot includes the chat model, embedding model, top-k, similarity threshold, temperature, chunk size, chunk overlap, both input-length limits, and, for this official dataset, the eight synthetic document titles. The runner searches only those titles and then applies the configuration’s permission rule. Other ready documents remain available in ordinary chat.

The scorer is `evaluate_trial` in `backend/app/evaluation/outcomes.py`. Rates are calculated in `backend/app/evaluation/metrics.py`. Infrastructure failures are excluded from rates. A rate is null when its denominator is zero. Percentage reduction is null when the baseline rate is zero or when either rate is missing. CSV export prefixes cells that could be read as spreadsheet formulas.

### Database access policy

Row-level security is enabled on the application tables. `anon` and `authenticated` are revoked from those tables, except `authenticated` may select its own profile. The API connects as the database owner, which bypasses row-level security, so the API is the authorisation boundary. This is stated in the migration and in `docs/limitations.md`.

## Partially implemented features

- Comparative experiments can be created and exported. One paired run has completed and is summarised in the evidence section. Its CSV and JSON files have not been written into the repository.
- Source excerpts are returned with chat answers. They are not a separate citation-quality evaluation. Secured excerpts pass through marker redaction. Baseline excerpts do not.
- Chunk size and overlap are recorded on the experiment, but they describe the index that already exists. Changing them does not reprocess documents unless a document is reprocessed.
- The analytics page can chart stored trials. It cannot show a comparison until a run has measured trials.
- Password reset and registration pages exist. This audit did not exercise them in a browser, and there is no automated test that a reset email is delivered.
- The project overview describes an OpenAI-compatible client. The configured provider at audit time was Gemini through that interface. The provider is an environment setting, not a hard-coded OpenAI deployment.

## Missing features

These items appear in the dissertation brief or would be needed for a complete empirical chapter. They are not in the implementation.

- There is no user role named HR. HR is a document access level. An employee cannot read an HR document unless that employee owns it or has an explicit grant. An administrator can read it.
- There is no automated browser test of a valid login, an invalid login, or logout.
- There is no screenshot set in the repository. The only image files found were inside `frontend/node_modules`.
- There is no saved CSV or JSON experiment export in the repository.
- There is no Git history, supervisor-meeting record, or 24-week timeline file.
- There is no continuous-integration workflow.
- The disclosure oracle does not score paraphrases. A lowercase marker on the baseline path is not counted, because baseline redaction is off and the scorer looks for the exact catalogue string.
- Prompt injection is not claimed to be eliminated. The secured prompt tells the model to ignore instructions in retrieved text. That is a construction control, not a measured guarantee that the model will obey it.
- The runner does not retry provider rate limits. A rate-limit response is an infrastructure failure and is excluded from the rates.

## Existing tests

Pytest modules and the checks they contain:

| File | What it checks | Depends on a live model? |
| --- | --- | --- |
| `backend/tests/test_access_control.py` | Token role is ignored. Document matrix, including employee denial of HR and administrator documents. Employee baseline chat is denied. Secured scope does not fall back to the full corpus. Baseline scope can include unauthorised ids. Retrieval rejects a missing allow-list. | No |
| `backend/tests/test_security_controls.py` | Configuration flags. Secured prompt separation. Input limits and non-blocking keyword labels. Upload type checks. Exact, case-variant, and zero-width marker redaction on the secured path only. Log scrubbing. NUL removal. | No |
| `backend/tests/test_evaluation.py` | Outcome labels, including attack success, blocked, false negative, false positive, inconclusive, and infrastructure failure. Null rates, zero-baseline reduction, latency percentile helper, CSV formula prefix, corpus restriction, chunking. | No. Numeric examples in this file are fixtures for the formula, not experimental findings. |
| `backend/tests/test_catalog.py` | Official title list, marker placement in the synthetic files, and coverage of the 15 seed keys. | No |
| `backend/tests/test_live_isolation.py` | Missing and forged tokens return 401 and write authentication-failure logs. An employee cannot read the four restricted synthetic documents. Secured retrieval with the stored HR embedding does not place those markers in the prompt. Baseline retrieval does place the HR marker in the system message. A forged unauthorised chunk is dropped before the secured model call and is kept on the baseline experiment path. An authorised document that quotes a forbidden marker still reaches the secured model; the returned answer and excerpt are redacted. The facilities-notice instruction stays in the user message. | Database, not the chat model. The model call is replaced in the pipeline test. |

Observed Pytest results in this workspace, not a saved CI report:

- `tests/test_security_controls.py`, `tests/test_live_isolation.py`, and `tests/test_access_control.py` completed with 15 passed.
- The suite as it stood before the later corpus-restriction tests completed with 30 passed.
- After the corpus-title tests were added, `tests/test_catalog.py` and `tests/test_evaluation.py` completed with 16 passed.

A full-suite run after the corpus-scope change had not been saved when this audit was written. Ruff reported a clean check on the security-review files after the import-order fix. Mypy was clean on 44 source files in an earlier check in this workspace, before the later runner changes. Those static-check results are session observations, not archived reports.

## Available experiment evidence

Observed on 13 November 2026 before the paired run started:

- Four synthetic profiles existed: administrator, two employees, and researcher.
- Eight synthetic documents were `ready`, each with one chunk.
- The official dataset contained the 15 catalogue cases and no extra cases.
- No experiment rows existed at that count.
- Six additional uploaded documents were also `ready`. Their access levels were employee, public, hr, admin, public, and public, with chunk counts 11, 50, 1, 2, 9, and 1. Their titles and contents are not repeated here. They are outside the eight-title snapshot used by the official runner. Ordinary chat can still retrieve them when the caller is allowed to read them.

The paired run “Synthetic suite paired run 2026-11-13” later completed. Comparison group `6a65fe15-9e7c-4ca8-8892-cf2d9584e655`. Both rows have status `completed`, progress 15/15, one repetition, and the shared snapshot recorded above. The engine’s report for those 30 stored trials is:

| Measure | Baseline | Secured |
| --- | --- | --- |
| Measured trials | 15 | 14 |
| Infrastructure failures excluded | 0 | 1 |
| Attack successes / attack trials | 8/11 (72.73%) | 0/10 (0%) |
| Disclosures / measured trials | 7/15 (46.67%) | 0/14 (0%) |
| Legitimate successes / benign trials | 4/4 (100%) | 4/4 (100%) |
| Mean latency | 8102 ms | 9437 ms |

The calculated attack-success reduction is 100%, and the disclosure reduction is 100%. That arithmetic uses the measured rates above. It is one repetition. The secured HR-disclosure trial was excluded because the provider returned unavailable (`The model provider is unavailable.`). Baseline indirect-injection trials were false negatives, not attack successes. Secured blocks were mostly `permission_filter_excluded_target_documents`; the direct administrator-code trial was `output_filter_redacted_marker`.

No CSV or JSON export file had been written into the repository when this section was updated. The rows are in `test_results`.

## Missing evidence required for the dissertation

1. The completed paired run exported to CSV and JSON. The trial rows exist in the database, but no export file is in the repository.
2. The calculated attack-success, disclosure, legitimate-task, and latency figures taken from that export, including nulls and infrastructure exclusions. Category breakdowns are required so input validation is not presented as a prompt-injection result.
3. The `decision_rule` and `model_emitted_markers` fields for each trial, so a blocked label can be distinguished from a model refusal.
4. Browser evidence for valid login, invalid login, and logout. The API test covers only a missing token and a forged token.
5. An authorisation demonstration for an administrator reading an HR document and for an employee being refused that document. The unit matrix covers the rule. A stored trial or a recorded interface check does not yet cover an HR-labelled document as a user journey.
6. Screenshots of the implemented screens, if the report is going to include figures of the interface. None are in the repository.
7. A project timeline. Git cannot supply one, because the folder is not a repository. Supervisor meetings and feedback were not found.
8. A fresh full Pytest run saved after the corpus-scope change, if the dissertation cites a single test count.
9. Enough repetitions, if the dissertation intends to discuss provider variability. The run in progress uses one repetition, which the design allows and which does not estimate variability.

## Potential technical limitations

- The secured condition changes several controls together. A difference cannot be assigned to one control without another experiment.
- The corpus is small and fictional. Top-k 8 with threshold -1 searches inside the allowed set rather than imitating a large production ranker.
- Exact marker scoring misses paraphrases. A marker echoed from the user question counts if it remains in the visible answer. Two direct-injection questions contain the marker string themselves.
- On the secured path, an attack whose target documents are outside the caller’s scope is classified as blocked when no forbidden marker remains visible, even if the model would also have refused. Baseline refusal in the same situation is a false negative, because the baseline does not exclude those documents. The outcome labels are therefore not interchangeable with “the model was successfully attacked” or “the model was successfully defended”.
- Infrastructure failures, including provider rate limits, timeouts, and a missing actor, are excluded from rates. They are not successful defences.
- Latency includes the measured path for a counted trial, including a rejected input. It is not a pure model-generation time.
- The database owner connection bypasses row-level security. A direct database session is not the same control as the API.
- Rate limiting and the experiment lock are process-local. One Uvicorn worker is assumed.
- Temperature 0 does not make the provider deterministic.
- Uploaded non-synthetic documents can affect chat even though the official experiment snapshot excludes them.
- Security logs can be changed by anyone with database access.

## Relevant source-code paths

Authentication and authorisation:

- `backend/app/deps.py`
- `backend/app/auth/jwt.py`
- `backend/app/auth/permissions.py`
- `frontend/middleware.ts`
- `frontend/lib/supabase.ts`

Documents and RAG:

- `backend/app/api/documents.py`
- `backend/app/rag/documents.py`
- `backend/app/rag/chunking.py`
- `backend/app/rag/llm.py`
- `backend/app/rag/retrieval.py`
- `backend/app/rag/pipeline.py`
- `backend/app/security/scope.py`
- `backend/app/security/prompts.py`
- `supabase/migrations/0001_init.sql`
- `supabase/migrations/0002_hr_access_level.sql`

Security controls:

- `backend/app/security/configurations.py`
- `backend/app/security/input_validation.py`
- `backend/app/security/output_validation.py`
- `backend/app/security/logging.py`
- `backend/app/security/rate_limit.py`
- `docs/security-controls.md`

Evaluation:

- `backend/app/evaluation/outcomes.py`
- `backend/app/evaluation/metrics.py`
- `backend/app/evaluation/runner.py`
- `backend/app/services/reporting.py`
- `backend/app/seed/catalog.py`
- `backend/scripts/run_experiment.py`
- `docs/methodology.md`
- `docs/evaluation-metrics.md`
- `docs/experimental-design.md`
- `docs/test-cases.md`
- `docs/limitations.md`

Interface:

- `frontend/app/(main)/dashboard/page.tsx`
- `frontend/app/(main)/documents/page.tsx`
- `frontend/app/(main)/chat/page.tsx`
- `frontend/app/(main)/research/page.tsx`
- `frontend/app/(main)/experiments/page.tsx`
- `frontend/app/(main)/analytics/page.tsx`
- `frontend/app/(main)/logs/page.tsx`
- `frontend/app/(main)/settings/page.tsx`
- `frontend/components/charts.tsx`

Research framing already written in the repository:

- `docs/research-question.md`
- `docs/project-overview.md`
- `docs/threat-model.md`
- `docs/system-architecture.md`
- `docs/database-design.md`
