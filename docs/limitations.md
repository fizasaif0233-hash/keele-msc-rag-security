# Limitations

## External validity

The corpus is small, fictional, and written so that the relevant phrases are easy to retrieve. A default top-k of 8 with a threshold of -1 examines access control inside that scope. It does not measure a large private corpus, a production ranker, or a threshold that drops most chunks. Results should not be stated as a property of RAG systems in general.

The secured condition changes several controls at once. A lower attack rate cannot be assigned to prompt wording alone, or to retrieval filtering alone, unless a further experiment changes one control.

## Measurement limits

Disclosure scoring uses exact marker strings. A model can leak the same fact in different words and be scored as no disclosure. It can also refuse while the baseline prompt still contained the restricted chunk. That refusal is a `false_negative`: the attack did not succeed, and the permission filter did not exclude the target. The dissertation should not describe every non-success as a control working.

The disclosure oracle remains an exact catalogue string in the visible answer. Secured redaction also removes a case variant or a marker with a zero-width character inserted. A spaced or paraphrased leak is neither redacted nor counted. Redaction can hide a marker that the metric then counts as not disclosed. The pre-redaction list is kept in `evaluation_details`. The official disclosure flag follows the user-visible text.

The oversized-input case defines acceptance as attack success. It is an input-control result. It should be reported within the input-validation category, not pooled into a claim about prompt injection without saying so. The category breakdown supports that distinction.

## Model and provider limits

Provider responses at temperature 0 can still vary. Context-window errors and timeouts are infrastructure failures. A missing API key leaves documents `pending` and does not create a security result. The application does not emulate the provider with a mock in the experiment path.

## Platform limits

- Authorisation in the API is mandatory because the database owner connection bypasses row-level security. RLS protects the Supabase Data API.
- Rate limits and the experiment lock live in one API process. Run one Uvicorn worker.
- Chat excerpts can include retrieved synthetic text. Baseline excerpts can include a marker. That is visible to the researcher who ran the baseline, and it is part of the experimental trace.
- Security logs can be edited by anyone with database access. They are operational records, not a sealed evidence store.
- The runner does not isolate network access. Tests are meaningful only against this deployment and this synthetic dataset.
- Email confirmation, redirect URLs, and the vector extension require Supabase project settings. The application cannot complete those steps from code.
- This repository does not contain experimental findings. Any rate shown in the interface after a run is a result of that run, not a result written into the source.
