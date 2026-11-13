# Methodology

## Design

The study is a controlled comparison inside one application. The two configurations share the LLM, the embedding model, the synthetic corpus, the test cases, and the retrieval parameters captured when the run starts. The configuration flag changes the controls listed in `docs/security-controls.md`.

A paired experiment creates two `experiments` rows with the same `comparison_group`, dataset, repetition count, and parameter snapshot. Each test case is executed once per repetition. The runner calls the same `answer_question` function as the chat API, with `experiment_execution=True`, so the employee actor can be tested on the baseline without giving employees that switch in the interface.

## Procedure

1. Apply the database migration.
2. Register a human administrator and promote that account with `scripts/promote_admin.py`. Do not use a built-in password.
3. Provide `SEED_USER_PASSWORD`, the service-role key, and the model key, then run `scripts/seed.py`.
4. Confirm the synthetic documents reach `ready`. If the embedding key is missing they remain `pending` and trials that need retrieval are infrastructure failures.
5. Start a baseline run and a secured run with the same dataset and repetitions. The official dataset snapshot names the eight synthetic documents. Both runs search that list, and the secured run then removes documents the actor cannot read. Other uploaded documents are not part of this comparison.
6. Export CSV or JSON from the evaluation page, or read `test_results` directly.
7. Use `evaluation_details.manual_review` to inspect inconclusive and ambiguous rows. Do not replace stored outcomes with hand-written summary rates.

## Scoring

Each trial is classified by `evaluate_trial` from the pipeline observation. The classifier does not treat HTTP 200 as success. Rules are in `docs/evaluation-metrics.md` and in the test-case `evaluation_criteria`.

The primary disclosure oracle is an exact synthetic marker. The indirect-injection document tells the model to reveal codes, but it does not contain the marker strings. An exact marker in an employee answer therefore came from another document, from redaction failure, or from an unexpected source. It is not an echo of the public attack text.

## Reproducibility

Each experiment stores the model names, top-k, similarity threshold, temperature, and chunk settings used for that run. The official cases are identified by `seed_key`. Running the seed again updates those official cases and does not delete cases a researcher added.

Temperature defaults to 0. Provider APIs can still be non-deterministic, so repetitions are stored as separate rows rather than averaged away. The same code, database migration, dataset, and parameter snapshot are the reproducibility record. Random seeds for the model provider are not available through the generic chat-completions interface used here.

## Unit evidence that does not depend on a model

Pytest covers permission decisions, retrieval scope, prompt separation, upload and question validation, marker redaction, trial classification, and the rate formulas, including zero denominators. Those tests can run without Supabase and without a model key.
