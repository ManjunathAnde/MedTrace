# 💊 MedTrace
### AI-Powered Medication Intelligence Platform

MedTrace is an AI-assisted medication investigation platform that combines deterministic medical evidence retrieval with structured LLM reasoning to generate evidence-grounded medication safety reports.

Instead of relying on an LLM to "know" medical information, MedTrace retrieves data from trusted public sources such as **RxNorm, DailyMed, and OpenFDA**, then uses AI only to classify requests and synthesize structured reports.

---

## Why MedTrace?

Modern LLMs are excellent at summarizing information but are unreliable as factual sources for healthcare applications.

MedTrace was built around a different philosophy:

> **Authoritative APIs retrieve the facts. AI explains the facts.**

This significantly reduces hallucination risk while still providing natural-language summaries that are easier to understand than raw FDA documentation.

---

## Example Workflow

```text
User Query
(accepts a natural-language medication question)
      │
      ▼
Safety Classification
(blocks unsafe medical advice before processing)
      │
      ▼
Medication Extraction
(identifies and normalizes the target medication)
      │
      ▼
Intent Classification
(determines what the user wants to investigate)
      │
      ▼
Profile Routing
(selects the minimum evidence needed for the request)
      │
      ▼
Evidence Retrieval
(fetches authoritative data from RxNorm, DailyMed & OpenFDA)
      │
      ▼
AI Risk Analysis
(synthesizes retrieved evidence into a structured report)
      │
      ▼
Medication Report
(displays evidence-grounded findings, warnings, recalls & adverse events)
```

---

# Key Features

- Multi-stage AI pipeline instead of a single monolithic prompt
- Evidence-first architecture using authoritative public medical sources
- Automatic Gemini → Groq provider failover
- Deterministic medication identity resolution through RxNorm
- Retrieval profiles that minimize unnecessary API calls
- Structured AI-generated medication reports
- Intelligent 72-hour report caching
- Responsive React frontend with real-time investigation timeline

---

# Architecture

```text
                React Frontend
                       │
                 POST /investigate
                       │
               FastAPI Backend
                       │
        ┌──────────────┴──────────────┐
        │                             │
 Safety Validation             Medication Extraction
        │                             │
        └──────────────┬──────────────┘
                       │
             Intent Classification
                       │
                 Profile Router
                       │
               Report Cache (72h)
                       │
                 Cache Hit?
             ┌─────────┴─────────┐
             │                   │
            Yes                 No
             │                   │
             │          Evidence Retrieval
             │         ┌────────┬────────┐
             │         │        │        │
             │      RxNorm  DailyMed  OpenFDA
             │         │        │        │
             │         └────────┴────────┘
             │                  │
             │          MedicationEvidence
             │                  │
             └────────► AI Risk Analyst
                              │
                     MedicationReport
```

---

# Design Decisions

### Evidence over Hallucination

Rather than asking an LLM for medication information directly, MedTrace retrieves evidence from authoritative medical databases first and limits the LLM's responsibility to summarization and reasoning.

---

### Specialized AI Stages

Instead of one large prompt, the system separates responsibilities into independent modules:

- Safety Classification
- Medication Extraction
- Intent Classification
- Risk Analysis

This makes each component easier to validate, debug, and improve independently.

---

### Graceful Failure

External AI providers occasionally fail due to rate limits or service outages.

To improve reliability:

- Gemini serves as the primary provider.
- Groq automatically handles transient provider failures.
- Module-specific fail-safe behavior prevents total request failure.

---

### Retrieval Profiles

Not every request requires every data source.

A profile router determines the minimum evidence required for each request, reducing latency and unnecessary API usage.

Example profiles include:

- Full Investigation
- Warnings Review
- Contraindications Review
- Recall Investigation
- Adverse Event Investigation

---

### Intelligent Caching

Successful investigations are cached for 72 hours using an in-memory TTL cache.
Repeated investigations for the same medication bypass:

- External API retrieval
- Evidence aggregation
- AI report generation

This significantly reduces response time and API usage.

---

# Technology Stack

### Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Axios

### Backend

- FastAPI
- Python
- Pydantic
- AsyncIO
- HTTPX

### AI

- Google Gemini
- Groq (automatic fallback)

### Medical Data Sources

- RxNorm
- DailyMed
- OpenFDA
- FDA Enforcement API

### Deployment

- Backend: Render
- Frontend: Vercel

---

# Reliability

MedTrace is designed to degrade gracefully rather than fail completely.
Examples include:

- Unsafe medical advice requests are rejected before retrieval begins.
- Medication identity is validated through RxNorm.
- Missing optional evidence sources reduce completeness rather than aborting the investigation.
- Automatic provider failover handles transient LLM outages.
- Cached investigations avoid unnecessary external calls.

---

# Trade-offs

Like any engineering system, MedTrace intentionally makes trade-offs.

**Chosen**

- Deterministic retrieval over AI-generated facts
- Modular AI pipeline over a single prompt
- Simplicity over distributed infrastructure
- Fast in-memory caching over persistent cache complexity


# Running Locally

```bash
git clone <repo>

cd MedTrace

pip install -r requirements.txt

uvicorn backend.main:app --reload
```

Required environment variables:

```env
GOOGLE_API_KEY=
GROQ_API_KEY=

GEMINI_MODEL=gemini-2.5-flash-lite
GROQ_MODEL=qwen/qwen3.6-27b
```

---

# Future Improvements

- Persistent distributed caching
- Authentication and user accounts
- Report history
- Drug-drug interaction engine
- Observability and metrics
- CI/CD pipeline

---

# Disclaimer

MedTrace is an educational software engineering project intended to demonstrate system design, AI orchestration, retrieval-augmented generation, and backend architecture.

It is **not** a substitute for professional medical advice or clinical decision-making.
