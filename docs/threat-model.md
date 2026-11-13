# Threat model

## Assets

- Synthetic documents and their embeddings.
- Role assignments and document grants.
- Chat history.
- Experiment results, which are the research evidence.
- Provider credentials and the Supabase service-role key.
- Security logs.

The corpus is fictional. The threat model still treats marker strings as protected because the experiment measures whether those strings cross an authorisation boundary.

## Actors

- An employee using their own session.
- A second employee, used for horizontal access tests.
- A researcher who can run both configurations and read aggregate results.
- An administrator who can change roles, access levels, and grants.
- The model provider, which receives prompts constructed by the server.
- An unauthenticated caller.

The browser is not a trusted source of roles or document permissions.

## In scope

- Direct prompt injection in the user question.
- Indirect prompt injection in a retrieved public document.
- Requests for confidential or administrator-only synthetic markers.
- A request that names another employee's document.
- A prompt that claims the caller is an administrator.
- Empty, oversized, and wrong-type uploads, and empty or oversized questions.
- Use of another user's chat identifier.
- Calling an administrator route with an employee token.

## Out of scope

- Compromise of Supabase, the database host, or the model provider.
- Theft of a legitimate session token from a user device.
- Attacks against the TLS endpoint or the hosting network.
- Training-data leakage of real secrets. The markers are synthetic and are not expected to exist in a model training set; an exact match is treated as evidence that the string was available to the model from this system.
- A claim that the model will follow the secured system prompt. The permission filter is the control that removes restricted text before the call.

## Trust boundaries

| Boundary | Assumption |
| --- | --- |
| Browser to API | The bearer token is verified. The body is not trusted for roles or grants. |
| API to database | Queries include the authorised document list. RLS blocks the public Data API. |
| API to model | The model sees only the prompt the server built. Restricted chunks must already have been removed in the secured configuration. |
| Retrieved text | Document text is data. It is not a system instruction in the secured configuration. |

## Residual risks

- The baseline configuration is intentionally weak on the RAG path. It is available to researchers and administrators, and to the experiment runner. It is not a production control.
- Output redaction only recognises exact synthetic markers. A paraphrase would not be redacted and might also fail the exact-match disclosure score. Both limits are recorded in `docs/limitations.md`.
- Rate limiting is in-memory and applies to one API process.
- Security logs are written by the application. They are not a tamper-proof audit trail against a database administrator.
