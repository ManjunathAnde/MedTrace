# 💊 MedTrace
### AI-Powered Medication Intelligence Platform

🔗 **[Live link ]([https://main.dy43b2jej051.amplifyapp.com](https://med-trace-liart.vercel.app/))** | **[GitHub](https://github.com/ManjunathAnde/MedTrace)** | **[LinkedIn](https://www.linkedin.com/in/manjunath-ande/)**
---
MedTrace is an AI-assisted medication investigation platform that combines deterministic medical evidence retrieval with structured LLM reasoning to generate evidence-grounded medication safety reports.

Instead of relying on an LLM to "know" medical information, MedTrace retrieves data from trusted public sources such as **RxNorm, DailyMed, and OpenFDA**, then uses AI only to classify requests and synthesize structured reports.

---

## Why MedTrace?

Modern LLMs are excellent at summarizing information but are unreliable as factual sources for healthcare applications.

MedTrace was built around a different philosophy:

> **Authoritative APIs retrieve the facts. AI explains the facts.**

The LLM never generates medication facts from its own training data. It only classifies intent and summarizes evidence that was already retrieved from RxNorm, DailyMed, and OpenFDA. If the evidence retrieval fails or returns nothing, the LLM has nothing to hallucinate from, it just reports incomplete data.

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
## ⚡ Intelligent Caching

To minimize repeated API calls and LLM inference, MedTrace caches **successful investigation reports** using **Upstash Redis**.

Redis was chosen over an in-memory cache because the backend is hosted on **Render**, whose free-tier instances may spin down after periods of inactivity. Since Redis lives independently of the application process, cached investigations survive cold starts and remain available across deployments.

### Profile-Aware Cache Policy

Instead of assigning every investigation the same lifetime, cache duration is determined by the freshness requirements of the underlying medical data.

| Investigation Profile | Cache TTL | Why? |
| :-------------------- | :-------: | :--- |
| 🔍 **Full Investigation** | **12 hours** | Includes FDA recall data, which is the most time-sensitive evidence source. |
| 🚨 **Recall Investigation** | **12 hours** | Recall information is safety-critical and updated more frequently than other datasets. |
| 📊 **Adverse Event Investigation** | **30 days** | OpenFDA FAERS data is released quarterly, making a 30-day cache well within the source's update cycle. |
| ⚠️ **Warnings Review** | **30 days** | Drug label warnings rarely change after approval. |
| ⛔ **Contraindications Review** | **30 days** | Contraindications are part of the approved FDA labeling and change infrequently. |
| 🔄 **Interaction Investigation** | **30 days** | Uses interaction information derived from drug labels rather than a continuously updated interaction database. |

Caching is treated purely as a **performance optimization**.

If Redis is unavailable, times out, or serialization fails, MedTrace simply performs the full investigation pipeline and returns a fresh report. A cache failure can never prevent an investigation from completing.

## Failover
The risk analysis stage has explicit failure handling. If Gemini fails (rate limits, timeouts, server errors), the request automatically retries on Groq. If Groq also fails, the module returns a fail-safe report instead of crashing.
 
Medication identity resolution through RxNorm is a hard dependency: if RxNorm is unavailable, the request returns an error rather than continuing with an unverified medication. This is intentional. A wrong medication identity makes the rest of the report meaningless, so failing loud here is safer than failing silent.

Other degradation behavior:
- Unsafe medical advice requests are rejected before any retrieval happens
- Missing optional evidence sources (DailyMed, OpenFDA) reduce report completeness rather than aborting the investigation
- Cached investigations skip external calls entirely (see Caching section for limitations on Render's free tier)

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
