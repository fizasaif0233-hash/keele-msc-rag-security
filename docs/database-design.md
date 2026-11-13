# Database design

The schema is `supabase/migrations/0001_init.sql`. Apply it in the Supabase SQL editor after the `vector` extension is available. The script does not delete existing rows.

## Tables

| Table | Purpose |
| --- | --- |
| `profiles` | Server-side role for each Supabase user. Roles are `admin`, `employee`, and `researcher`. |
| `documents` | Owner, access level, processing status, extracted text, content hash, and detected synthetic markers. |
| `document_permissions` | Explicit read grants. These do not change a user's role. |
| `document_chunks` | Chunk text, metadata, and a `vector(1536)` embedding. |
| `chat_sessions`, `chat_messages` | Per-user chat history, latency, and source metadata. |
| `test_datasets`, `test_cases` | Named datasets and cases. Machine-readable rules live in `evaluation_criteria`. |
| `experiments` | One row per configuration run, with the parameter snapshot and progress counters. |
| `test_results` | One row per trial, including outcome flags and `evaluation_details`. |
| `security_logs` | Structured security events. Metadata is scrubbed before insert. |
| `app_settings` | Non-secret runtime settings. |

`documents` has a unique pair of owner and content hash so the same account cannot upload the same file twice. `test_results` is unique on experiment, test case, and repetition.

## Retrieval

`match_document_chunks(query_embedding, match_count, similarity_threshold, allowed_document_ids)` joins ready chunks to documents and keeps rows whose identifier is in `allowed_document_ids`. A null or empty list matches nothing. The application never requests an unfiltered search. Similarity is `1 - cosine distance`, and an HNSW index uses `vector_cosine_ops`.

The embedding width is 1536, matching `EMBEDDING_DIMENSIONS` and the default `text-embedding-3-small` model. A different width requires a new migration and a matching model.

## Access levels

| Level | Who can read, before explicit grants |
| --- | --- |
| `public` | Any authenticated user |
| `employee` | Employees, researchers, and administrators |
| `confidential` | The owner, an explicit grantee, or an administrator |
| `admin` | An administrator, the owner, or an explicit grantee |

Ownership and explicit grants are checked in `can_read_document`. The RAG scope uses the same rule for the secured configuration.

## Row-level security

RLS is enabled on every application table. The anon and authenticated Data API roles are revoked, except that an authenticated user may select their own profile. There is no policy that lets a user update `profiles.role`.

The FastAPI service connects with the database password. In Supabase that role bypasses RLS, so the API enforces authorisation in Python and in the retrieval query. RLS is the barrier against use of the public Data API, not a substitute for the API checks.

## Profile creation

`handle_new_user` inserts a profile with role `employee` when Supabase creates an `auth.users` row. On conflict it updates the email and does not change the role, so a later auth event cannot demote an administrator.

## Additional columns

The implementation adds columns the evaluation needs and the original field list did not name: content hash, extracted text, processing error, protected markers, chunk count, experiment parameters, progress, comparison group, and result error text. Security-log metadata and chat-message metadata are JSON so the listed fields can be stored without adding secret material.
