# User guide

## Roles

| Role | Main tasks |
| --- | --- |
| Employee | View authorised documents, upload only when an administrator enables employee uploads, and ask questions through the secured chat. |
| Researcher | Manage datasets and cases, run both configurations, read evaluation results and security logs, and use baseline chat for inspection. |
| Administrator | All researcher tasks, plus roles, document access, explicit grants, and settings changes. |

An employee who opens a researcher URL receives an authorisation error from the API. Hiding a navigation link is not the control.

## Documents

Upload a `.txt` or `.pdf` file and choose an access level. Administrators can choose confidential or admin. Other uploaders can choose public or employee. The document page shows the owner, processing status, chunk count, detected markers, and extracted text when the caller is allowed to read it.

`pending` means the text was stored but embeddings were not created. Configure the model key and use Reprocess. `failed` means extraction or embedding did not succeed; the error text is the safe message returned by the server.

Administrators change access level and grant read access by email. A grant does not change the recipient's role. Deleting a document removes its chunks and permission rows.

## Chat

Create a session, optionally tick documents, and ask a question. With no documents ticked, the secured configuration searches documents the account may read. The baseline configuration searches the ready corpus. That difference is intentional and is explained on the page.

Answers show latency, warnings, and source titles. A secured warning about redaction means an exact unauthorised marker was removed. It does not mean prompt injection has been solved. Employees cannot select the baseline configuration.

## Research cases

Filter the seeded cases by category. The expected outcome is the human-readable rule. The stored evaluation criteria are what the runner uses. When adding a case, provide JSON criteria. A vague case can come back `inconclusive` and should be reviewed rather than treated as a pass.

## Experiments

Select the dataset, the repetition count, and one or both configurations. Optional top-k, threshold, and temperature override the saved settings for that run only. Both rows of a paired run receive the same overrides.

Open a run to see progress. The page refreshes while the status is `running`. A failed run can be resumed; completed runs are kept and are not overwritten. Create a new run to repeat a completed comparison.

The command-line equivalent, from `backend`, is:

```powershell
.\.venv\Scripts\python scripts\run_experiment.py --email researcher.synthetic@keele-rag.example --name "Paired run" --configurations baseline secured --repetitions 1
```

The email must belong to a researcher or administrator. The command waits until the trials have been stored.

## Evaluation

The evaluation page shows attack success, disclosure, legitimate-task success, and latency for each configuration when measured trials exist. Export CSV or JSON before using the figures in the dissertation. CSV columns include the test identifier, category, description, configuration, expected and actual outcomes, attack and disclosure flags, legitimate-task success, latency, error, timestamp, and repetition.

Read `false_negative`, `inconclusive`, and `infrastructure_failure` in the trial table before summarising a run. The decision rule and the manual-review flag are on the experiment page and in the JSON export.

## Logs and settings

Security logs show the time, user, event, configuration, outcome, severity, and a related experiment or test identifier when one was recorded. Settings show whether the database, Supabase, and model key are present without revealing the values. Administrators can change model names, chunk size, overlap, top-k, similarity threshold, temperature, input limits, upload size, rate limit, and the employee-upload switch. Changing the embedding width is not a setting. It requires a database migration.
