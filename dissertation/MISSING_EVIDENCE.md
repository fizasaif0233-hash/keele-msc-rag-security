# Evidence status

The dissertation uses the paired run stored on 13 November 2026. The export of that run was written locally on 18 November 2026. Do not invent experimental numbers, and do not backdate the export.

## Present on this computer

1. `dissertation/EVIDENCE/paired-run-2026-11-13.csv`
2. `dissertation/EVIDENCE/paired-run-2026-11-13.json`
3. `dissertation/EVIDENCE/pytest-2026-11-18.txt`

These files are the source of Appendix J and are stored with the project. `backend/requirements.lock.txt` was frozen from the local environment on 19 November 2026. It is not a reconstruction of the environment used on 13 November 2026.

The export counts match Chapter 6: baseline attack success 8/11 and disclosure 7/15; secured attack success 0/10 and disclosure 0/14. One secured trial was excluded because the provider was unavailable.

## Still not done

1. A second repetition. The reported run uses one repetition.
2. A stored chat trial against an HR-labelled document. The paired human-resources case uses the confidential policy.
3. A scored model ablation. The code defines permission-only, prompt-separation-only, and redaction-only configurations, and unit tests check each one without calling the model. A Gemini ablation was not run, so Chapter 6 is still the whole-bundle comparison.
4. Five repetitions and a larger indirect-injection suite. The reported run uses one repetition, and the indirect cases remain 0 of 2 on both paths.
