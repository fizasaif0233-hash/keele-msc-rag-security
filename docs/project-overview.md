# Project overview

This repository is an individual MSc system-development project. It implements a research application for comparing two retrieval-augmented generation (RAG) configurations in a web application:

- a baseline configuration with deliberately limited application-level controls;
- a secured configuration that applies authentication, document authorisation, permission-filtered retrieval, separation of trusted and untrusted text, input handling, output checks, and security-event logging.

The application is not a general-purpose chatbot. It stores documents, embeddings, chats, test cases, experiment trials, and security logs so that a researcher can produce trial-level evidence. Dashboard figures are calculated from those records. The software does not ship with fabricated attack-success rates.

The corpus, user names, departments, and protected strings are fictional. The protected strings, such as `SYNTHETIC_HR_SECRET_001`, are scoring oracles. They are not real secrets.

## What the software contains

- A Next.js research interface for authentication, documents, chat, test management, experiments, analytics, logs, and settings.
- A FastAPI service that verifies Supabase access tokens and enforces authorisation on the server.
- A PostgreSQL schema for Supabase, including pgvector similarity search and row-level security that denies direct Data API access to application tables.
- An OpenAI-compatible client for chat completions and embeddings.
- A Pytest suite for authorisation, retrieval scope, prompt construction, input and output checks, and metric calculation. These tests do not ask a model to judge the result.
- A repeatable experiment runner with CSV and JSON export.

## What it does not claim

Prompt injection cannot be shown to be eliminated by this system. Output checks can miss paraphrases, and a model can refuse an attack even when a weak configuration has retrieved restricted text. Those outcomes are recorded separately. Infrastructure failures, such as a missing API key or a provider timeout, are not counted as successful defences.
