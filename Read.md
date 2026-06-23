# Medication Intelligence Agent

> This document is the source of truth for the project.
>
> Before implementing any feature, read this file and ensure new work aligns with the architectural decisions documented here.
>
> If proposed code conflicts with this document, the document takes precedence unless the architecture is intentionally revised.

---

# 1. Project Overview

Medication Intelligence Agent is an AI-powered healthcare application that investigates medications using authoritative public healthcare APIs and generates evidence-backed intelligence reports.

The system answers questions such as:

```text
Investigate Ozempic
Why was Drug X recalled?
What are the warnings for Metformin?
What interactions does Warfarin have?
What adverse events have been reported for Wegovy?
```

The system is NOT intended to:

- Diagnose conditions
- Recommend treatments
- Replace healthcare professionals
- Provide patient-specific medical advice

The system IS intended to:

- Investigate medications
- Aggregate evidence from trusted healthcare sources
- Analyze medication safety information
- Explain findings in an understandable format
- Demonstrate modern AI classification and deterministic execution

---

# 2. Core Philosophy

## APIs Are The Source Of Truth

The system does not trust the LLM as the source of medical facts.

```text
Healthcare APIs
        ↓
Evidence Collection
        ↓
Gemini Analysis
        ↓
Final Report
```

All factual information originates from external healthcare APIs.

Gemini's role is classification and reasoning only.

Gemini must never invent medical facts.

---

# 3. Guiding Principle

When uncertain about where a responsibility belongs, ask:

> Should this belong to Gemini or deterministic software?

If the task involves reasoning, interpretation, prioritization, or understanding intent → **Gemini**

If the task involves retrieval, normalization, validation, orchestration, or structured processing → **Deterministic software**

This principle guides all architectural decisions.

---

# 4. High-Level Architecture

```text
User Query
        ↓
Safety Filter
        ↓
Gemini Intent Classifier
        ↓
Retrieval Profile Selection
        ↓
Deterministic Evidence Collection
        ↓
Evidence Validation
        ↓
Evidence Aggregation Layer
        ↓
Gemini Risk Analyst
        ↓
Structured Response
```

---

# 5. Why This Architecture?

The project intentionally avoids two extremes.

## Extreme 1: Simple LLM Wrapper

```text
User → Gemini → Answer
```

Problems:

- No grounded evidence
- Hallucinations
- No transparency
- Weak engineering story

---

## Extreme 2: Fully Autonomous Agent

```text
User → Gemini → Tool Planning → Tool Selection → Tool Sequencing → Answer
```

Problems:

- Hard to debug
- Hard to evaluate
- Unpredictable
- Adds complexity without clear value

---

## Chosen Approach

```text
Gemini = Classifier + Analyst
Retrieval Profiles = Deterministic Executors
APIs = Source of Truth
```

Gemini decides what the user is asking and what findings matter.

Retrieval profiles decide which APIs are called, in what order, and how evidence is structured.

---

# 6. Safety Filter

All user queries pass through a safety filter before intent classification.

The application does not process queries requesting:

- Diagnoses
- Treatment recommendations
- Medication recommendations
- Patient-specific medical advice
- Instructions to start or stop medications

## Safety Filter Strategy

```text
Step 1: Rule-Based Check
        ↓
If match found → return safety response immediately
Do not proceed further

Step 2: Gemini Safety Fallback
If no rule match → Gemini classifies as SAFE or UNSAFE
UNSAFE → return safety response
SAFE → proceed to intent classification
```

## Blocked Patterns (Rule-Based)

```python
BLOCKED_PATTERNS = [
    "should i take",
    "should i stop",
    "what medication should",
    "do i need",
    "recommend me",
    "what treatment",
    "can i take",
    "is it safe for me"
]
```

## Why Hybrid?

Rules handle obvious cases instantly at zero cost.

Gemini handles edge cases rules miss.

Example rules miss:

```text
"my doctor told me to quit this drug, thoughts?"
```

Gemini catches it. Rules do not.

---

# 7. Gemini Responsibilities

Gemini has exactly three responsibilities.

---

## Responsibility 1: Safety Classification (Fallback)

When rule-based safety filter passes without a match, Gemini classifies the query as SAFE or UNSAFE.

Gemini does not process UNSAFE queries further.

---

## Responsibility 2: Intent Classification

Gemini classifies the user query and selects one of the predefined retrieval profiles.

```text
"Investigate Ozempic"          → full_investigation
"What are the warnings?"       → warnings_review
"Has this been recalled?"      → recall_investigation
"What interactions exist?"     → interaction_investigation
"What adverse events?"         → adverse_event_investigation
"Who should not take this?"    → contraindications_review
```

Gemini does NOT:

- Select APIs
- Determine API order
- Generate execution plans
- Create new profiles
- Perform autonomous tool planning

The backend owns all retrieval logic.

---

## Responsibility 3: Evidence Analysis

After evidence collection is complete, Gemini:

- Prioritizes findings
- Identifies important risks
- Explains significance
- Generates structured reports

Gemini is not the source of medical facts.

All factual information must originate from authoritative healthcare APIs.

---

# 8. Retrieval Profiles

Retrieval profiles are deterministic.

For a given profile:

- APIs are predefined
- API order is predefined
- Evidence structure is predefined
- Output format is predefined

Retrieval behavior does not vary between executions.

## Profile Mapping Table

| Profile | Sources |
|---|---|
| Full Investigation | RxNorm → DailyMed → FDA Recall → OpenFDA → RxNav |
| Warnings Review | RxNorm → DailyMed |
| Contraindications Review | RxNorm → DailyMed |
| Recall Investigation | RxNorm → FDA Recall |
| Interaction Investigation | RxNorm → RxNav |
| Adverse Event Investigation | RxNorm → OpenFDA |

---

## Profile 1: Full Investigation

Example Queries:

```text
Investigate Ozempic
Analyze Metformin
Tell me everything important about Wegovy
```

Execution Plan:

```text
RxNorm
        ↓
DailyMed
        ↓
FDA Recall
        ↓
OpenFDA
        ↓
RxNav
        ↓
Evidence Aggregation
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Full Investigation Report

---

## Profile 2: Warnings Review

Example Queries:

```text
What are the warnings for Ozempic?
Does Wegovy have any serious warnings?
```

Execution Plan:

```text
RxNorm
        ↓
DailyMed
        ↓
Warnings Extraction
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Warnings Report

---

## Profile 3: Contraindications Review

Example Queries:

```text
What are the contraindications for Ozempic?
Who should not take Wegovy?
```

Execution Plan:

```text
RxNorm
        ↓
DailyMed
        ↓
Contraindications Extraction
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Contraindications Report

---

## Profile 4: Recall Investigation

Example Queries:

```text
Has Ozempic ever been recalled?
Why was Drug X recalled?
```

Execution Plan:

```text
RxNorm
        ↓
FDA Recall Data
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Recall Report

---

## Profile 5: Interaction Investigation

Example Queries:

```text
What interactions does Ozempic have?
Are there serious interactions with Metformin?
```

Execution Plan:

```text
RxNorm
        ↓
RxNav
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Interaction Report

---

## Profile 6: Adverse Event Investigation

Example Queries:

```text
What adverse events have been reported for Ozempic?
What safety concerns exist for Wegovy?
```

Execution Plan:

```text
RxNorm
        ↓
OpenFDA
        ↓
Evidence Validation
        ↓
Gemini Analysis
```

Output: Adverse Event Report

---

# 9. Report Schemas

Every profile must produce a report that conforms to its schema.

Gemini must populate these exact sections. No improvisation.

---

## Full Investigation Report

```text
1. Medication Overview
   - Drug name, generic name, drug class

2. Key Safety Findings
   - Most critical findings prioritized

3. Warnings
   - Boxed warnings
   - Major precautions

4. Contraindications
   - Who should not take this medication

5. Drug Interactions
   - Known interactions and severity

6. Recall History
   - Active or historical recalls

7. Adverse Event Signals
   - Most frequently reported events
   - Note: reports do not establish causation

8. Evidence Limitations
   - Failed sources
   - Completeness score

9. Sources Used
   - List of APIs that returned data
```

---

## Warnings Report

```text
1. Medication Overview

2. Boxed Warnings
   - Full text of boxed warnings if present

3. Major Precautions
   - Key safety precautions

4. Evidence Limitations

5. Sources Used
```

---

## Contraindications Report

```text
1. Medication Overview

2. Absolute Contraindications
   - Situations where drug must not be used

3. Relative Contraindications
   - Situations requiring caution

4. Evidence Limitations

5. Sources Used
```

---

## Recall Report

```text
1. Recall Summary
   - Current recall status

2. Recall Timeline
   - Dates of recall actions

3. Recall Reasons
   - Why the recall occurred

4. Severity Classification
   - FDA recall class (I, II, III)

5. Regulatory Notes
   - Actions taken

6. Sources Used
```

---

## Interaction Report

```text
1. Medication Overview

2. High Severity Interactions
   - Interactions requiring immediate attention

3. Moderate Severity Interactions

4. Low Severity Interactions

5. Evidence Limitations

6. Sources Used
```

---

## Adverse Event Report

```text
1. Medication Overview

2. Most Frequently Reported Events
   - Events ranked by frequency

3. Serious Event Signals
   - Events flagged as serious

4. Important Disclaimer
   - Adverse event reports do not establish causation

5. Evidence Limitations

6. Sources Used
```

---

# 10. Evidence Package

All API responses must be normalized into a canonical evidence structure before being provided to Gemini.

```text
MedicationEvidence
        ├── DrugIdentity
        ├── LabelEvidence
        ├── RecallEvidence
        ├── AdverseEventEvidence
        ├── InteractionEvidence
        └── EvidenceMetadata
```

The evidence package is the single source of truth for report generation.

Gemini consumes structured evidence, not raw API responses.

## Evidence Contracts

```python
DrugIdentity:
    input_name: str
    generic_name: str
    rxcui: str
    brand_names: list[str]

LabelEvidence:
    boxed_warnings: list[str]
    contraindications: list[str]
    precautions: list[str]

RecallEvidence:
    recalls: list[RecallRecord]
    total_count: int

RecallRecord:
    recall_number: str
    reason: str
    classification: str
    date: str
    status: str

AdverseEventEvidence:
    events: list[AdverseEvent]
    total_count: int

AdverseEvent:
    term: str
    count: int
    serious: bool

InteractionEvidence:
    interactions: list[DrugInteraction]
    total_count: int

DrugInteraction:
    drug_name: str
    severity: str
    description: str

EvidenceMetadata:
    sources_attempted: int
    sources_succeeded: int
    sources_failed: list[str]
    completeness_score: float
    retrieved_at: datetime

MedicationEvidence:
    drug_identity: DrugIdentity
    label_evidence: LabelEvidence | None
    recall_evidence: RecallEvidence | None
    adverse_event_evidence: AdverseEventEvidence | None
    interaction_evidence: InteractionEvidence | None
    metadata: EvidenceMetadata
```

---

# 11. Evidence Validation

Before report generation, evidence must be validated.

Validation checks:

- Missing required fields
- Failed API calls
- Empty evidence sections
- Data inconsistencies
- Normalization errors

Evidence validation prevents incomplete or malformed evidence from reaching Gemini.

---

# 12. Evidence Completeness Scoring

```text
completeness_score = sources_succeeded / sources_attempted
```

Example:

```json
{
  "sources_attempted": 5,
  "sources_succeeded": 4,
  "sources_failed": ["OpenFDA"],
  "completeness_score": 0.80
}
```

Reports must clearly indicate unavailable sources.

Users must be able to distinguish between:

- No evidence found
- Evidence source unavailable

---

# 13. External Data Sources

---

## RxNorm

Purpose: Drug normalization

Provides:

- Generic names
- Brand names
- RxCUI identifiers

Example:

```text
Ozempic → Semaglutide
```

Status: **Critical** — if RxNorm fails, the investigation terminates immediately.

---

## DailyMed

Purpose: Official prescribing information

Provides:

- Drug labels
- Boxed warnings
- Contraindications
- Precautions

Status: Primary

---

## FDA Recall Database

Purpose: Regulatory recall information

Provides:

- Active recalls
- Recall classifications
- Recall reasons
- Recall dates

Status: Primary

---

## OpenFDA

Purpose: Safety event information

Provides:

- Adverse event reports
- Safety signals
- Historical reporting data

Important: Adverse event reports do NOT prove causation. The application must communicate this clearly in every report.

Status: Supplemental

---

## RxNav

Purpose: Drug interaction information

Provides:

- Interaction detection
- Interaction severity
- Related medications

Status: Supplemental

---

# 14. API Failure Strategy

```text
Critical:     RxNorm
Primary:      DailyMed, FDA Recall
Supplemental: OpenFDA, RxNav
```

If RxNorm fails → investigation terminates, error returned to user.

If a primary source fails → investigation continues, failure recorded, completeness score reduced.

If a supplemental source fails → investigation continues, failure recorded, completeness score reduced.

---

# 15. Caching Strategy

Use in-memory TTL cache via `cachetools`. No external infrastructure required.

TTL for all sources: 24 hours

```python
from cachetools import TTLCache
cache = TTLCache(maxsize=100, ttl=86400)
```

Cache is keyed by normalized drug name per API client.

Cache resets on server restart — acceptable for this deployment scope.

---

# 16. Evaluation Strategy

A project without evaluation is a demo. A project with evaluation is engineering.

---

## Evaluation Dataset

Create a dataset of 25 medications in `backend/evaluation/dataset.json`.

For each entry:

```json
{
  "drug_name": "Metformin",
  "expected_generic_name": "metformin",
  "known_recall_status": "no active recalls",
  "known_major_warnings": ["lactic acidosis"],
  "known_contraindications": ["renal impairment"],
  "known_interactions": ["contrast dye", "alcohol"]
}
```

---

## Retrieval Validation

Verify:

- RxNorm returns correct generic names
- DailyMed returns expected warnings
- FDA returns expected recall information
- RxNav returns expected interactions

---

## Report Validation

Evaluate:

- Did Gemini include critical findings?
- Did Gemini omit important findings?
- Did Gemini hallucinate?
- Did Gemini explain findings accurately?

---

# 17. Technology Stack

---

## Frontend

- React
- TypeScript
- Tailwind CSS

---

## Backend

- FastAPI
- Python 3.11+
- httpx for all API calls
- Pydantic v2 for all data models
- cachetools for in-memory caching
- python-dotenv for environment variables

---

## LLM

- Gemini 2.5 Flash
- Responsibilities: Safety Classification (fallback) + Intent Classification + Evidence Analysis

---

## Frameworks

Do NOT introduce without explicit approval:

- LangGraph
- CrewAI
- AutoGen
- Any multi-agent framework

Current architecture does not require them.

---

# 18. Folder Structure

```text
medication-intelligence-agent/
        ├── .env.example
        ├── .gitignore
        ├── requirements.txt
        ├── README.md
        ├── CLAUDE.md
        ├── backend/
        │       ├── __init__.py
        │       ├── main.py
        │       ├── llm/
        │       │       ├── __init__.py
        │       │       ├── intent_classifier.py
        │       │       ├── safety_classifier.py
        │       │       └── risk_analyst.py
        │       ├── profiles/
        │       │       ├── __init__.py
        │       │       ├── full_investigation.py
        │       │       ├── warnings_review.py
        │       │       ├── contraindications_review.py
        │       │       ├── recall_investigation.py
        │       │       ├── interaction_investigation.py
        │       │       └── adverse_event_investigation.py
        │       ├── apis/
        │       │       ├── __init__.py
        │       │       ├── rxnorm.py
        │       │       ├── dailymed.py
        │       │       ├── fda_recall.py
        │       │       ├── openfda.py
        │       │       └── rxnav.py
        │       ├── models/
        │       │       ├── __init__.py
        │       │       └── evidence.py
        │       ├── safety/
        │       │       ├── __init__.py
        │       │       └── filter.py
        │       └── evaluation/
        │               └── dataset.json
        └── frontend/
```

Note: `agents/` renamed to `llm/` — this system is not an autonomous agent. Gemini performs classification and analysis only.

---

# 19. Environment Variables

```env
GOOGLE_API_KEY=your_google_api_key_here
```

No other API keys required. All healthcare APIs are public and free.

---

# 20. Installation

```bash
pip install fastapi uvicorn httpx pydantic cachetools google-generativeai python-dotenv
```

---

# 21. Out Of Scope

Version 1 must NOT include:

- Drug comparison (moved to future enhancements)
- Diagnosis
- Treatment recommendations
- Patient-specific advice
- Autonomous tool planning
- Multi-agent architectures
- RAG
- Vector databases
- Knowledge graphs
- Long-term memory

Avoid feature creep.

---

# 22. Future Enhancements

Consider after V1 is complete and deployed:

- Drug Comparison (Profile 7)
- Adverse event trend analysis
- Drug class comparisons
- Recall notification system
- Larger evaluation dataset

---

# 23. Development Workflow

Every implementation task must follow this sequence.

**Step 1** — Read README.md and CLAUDE.md fully.

**Step 2** — Inspect existing code and folder structure.

**Step 3** — Explain understanding of current implementation.

**Step 4** — Propose implementation plan:
- Files to create or modify
- Components affected
- Architecture impact
- Potential risks

**Step 5** — Validate plan:
- Does it preserve deterministic profiles?
- Does it preserve API-first evidence gathering?
- Does it keep Gemini responsibilities limited to classification and analysis?

**Step 6** — Wait for approval. Do not write code before approval.

**Step 7** — Implement only the approved plan.

**Step 8** — Verify: functionality, architecture alignment, error handling, type safety.

**Step 9** — Summarize: what changed, why it changed, how it was verified.

---

# 24. One-Sentence Description

Built an AI-powered Medication Intelligence Agent that uses authoritative healthcare APIs to investigate medications, analyze recalls, warnings, adverse events, and interactions, and generates evidence-backed medication safety reports through LLM-based intent classification and deterministic retrieval profile execution.