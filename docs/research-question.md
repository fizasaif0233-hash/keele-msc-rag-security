# Research question

## Question

To what extent do a defined set of application-level controls reduce prompt-injection success and unauthorised disclosure in a RAG web application, relative to a baseline that uses the same model, embeddings, corpus, test cases, and retrieval settings?

## Why the question matters

RAG applications place retrieved text into a model prompt. Retrieved documents and user questions are untrusted, but a weak integration can treat them as instructions. Indirect prompt injection has been demonstrated against LLM-integrated applications by placing instructions in content that the application later retrieves (Greshake et al., 2023). Direct instruction override is a related failure mode (Perez and Ribeiro, 2022). OWASP identifies prompt injection as a principal risk for LLM applications (OWASP Foundation, 2025).

A RAG system also introduces an access-control problem. If retrieval ignores document permissions, the model can receive text the caller is not allowed to read. Asking the model to respect those permissions is not an access-control mechanism, because the model has already seen the text and cannot be relied on to enforce policy.

Lewis et al. (2020) introduced retrieval-augmented generation as a way to condition generation on retrieved passages. That architecture is useful for private document question answering, and it is also the point at which document permissions and untrusted content meet the model.

## What this project compares

The independent variable is the security configuration. The secured configuration adds the controls listed in `docs/security-controls.md`. The baseline keeps authentication and document-management authorisation, because disabling those would create an unnecessarily exposed system, but it does not filter RAG retrieval by permission and it does not separate retrieved text from trusted instructions.

The dependent measures are attack success, sensitive-marker disclosure, legitimate-task success, and response latency. Definitions are in `docs/evaluation-metrics.md`.

## Boundary of the claim

A result from this application is evidence about this implementation, this synthetic corpus, this model, and these test cases. It is not a general proof that the controls defeat prompt injection. NIST's AI Risk Management Framework treats measurement and residual risk as ongoing activities rather than as a one-time guarantee (NIST, 2023).

## References

Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T. and Fritz, M. (2023) 'Not what you've signed up for: compromising real-world LLM-integrated applications with indirect prompt injection'. arXiv:2302.12173. Available at: https://arxiv.org/abs/2302.12173 (Accessed: 13 November 2026).

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S. and Kiela, D. (2020) 'Retrieval-augmented generation for knowledge-intensive NLP tasks', Advances in Neural Information Processing Systems, 33. Available at: https://arxiv.org/abs/2005.11401 (Accessed: 13 November 2026).

National Institute of Standards and Technology (2023) Artificial Intelligence Risk Management Framework (AI RMF 1.0). NIST AI 100-1. Available at: https://doi.org/10.6028/NIST.AI.100-1 (Accessed: 13 November 2026).

OWASP Foundation (2025) OWASP Top 10 for Large Language Model Applications. Available at: https://owasp.org/www-project-top-10-for-large-language-model-applications/ (Accessed: 13 November 2026).

Perez, F. and Ribeiro, I. (2022) 'Ignore previous prompt: attack techniques for language models'. arXiv:2211.09527. Available at: https://arxiv.org/abs/2211.09527 (Accessed: 13 November 2026).
