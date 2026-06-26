# CLAUDE.md

This file contains instructions for Claude Code when working on the Medication Intelligence Agent project.

Read this file before making architectural decisions, implementing features, or modifying existing code.

---

# Primary Goal

The goal is NOT to maximize feature count.

The goal is to build a clean, explainable, production-style AI application that demonstrates:

* Workflow orchestration
* Tool integration
* API-driven evidence collection
* LLM reasoning
* Evaluation discipline
* Strong software engineering practices

When choosing between:

```text
More Features
```

and

```text
Cleaner Architecture
```

always choose cleaner architecture.

---

# Development Philosophy

The project follows a strict principle:

```text
AI for reasoning

Software for execution
```

Gemini should perform:

* Intent classification
* Risk prioritization
* Explanation generation
* Comparative analysis

Traditional software should perform:

* API calls
* Data validation
* Data normalization
* Routing
* Error handling
* Workflow orchestration
* Evidence aggregation

Never move deterministic logic into the LLM unless there is a compelling reason.

---

# Before Writing Code

For every task:

## Step 1

Read README.md.

Treat README.md as the architectural source of truth.

---

## Step 2

Inspect existing code.

Before proposing changes:

Understand:

* Project structure
* Existing abstractions
* Existing patterns
* Existing dependencies

Avoid introducing duplicate patterns.

---

## Step 3

Create an implementation plan.

Before writing code, explain:

### Objective

What problem is being solved?

### Files

Which files will be modified?

### Architecture Impact

How does the change fit into the existing architecture?

### Risks

What could break?

### Alternatives

Were simpler approaches considered?

---

## Step 4

Wait for approval.

Do not immediately begin coding after generating a plan.

Allow the user to review and approve the plan first.

---

# Architecture Rules

---

## Rule 1

Do Not Create Autonomous Agents

Avoid:

```text
LLM
↓
Dynamic Tool Planning
↓
Dynamic Tool Selection
↓
Dynamic Execution
```

unless explicitly requested.

The project uses predefined workflows.

---

## Rule 2

Preserve Deterministic Workflows

Once a workflow is selected:

* Tool sequence should be predictable
* API sequence should be predictable
* Evidence structure should be predictable

Determinism is preferred over unnecessary flexibility.

---

## Rule 3

APIs Are The Source Of Truth

Never rely on Gemini's internal knowledge when API data exists.

Always prefer:

```text
API Evidence
↓
Gemini Analysis
```

over:

```text
Gemini Knowledge
```

---

## Rule 4

Structure Data Before LLM Calls

Avoid passing raw API responses directly to Gemini.

Always:

```text
API Responses
↓
Normalization
↓
Structured Evidence Package
↓
Gemini
```

This improves:

* Reliability
* Debuggability
* Evaluation

---

## Rule 5

Avoid Framework Creep

Do NOT introduce:

* LangGraph
* CrewAI
* AutoGen
* Haystack
* LlamaIndex

without explicit approval.

The project should remain understandable without specialized agent frameworks.

---

## Rule 6

Classifiers Do Not Override Themselves

The Intent Classifier never overrides its own prediction.

Confidence routing belongs to the orchestration layer.

The classifier's only job is to return a profile and a confidence score.
What to do with low confidence is the orchestrator's decision, not the classifier's.

---

# Code Quality Standards

---

## Type Safety

Prefer strong typing.

Use:

* Pydantic models
* Type hints
* Explicit schemas

Avoid loosely structured dictionaries when a model is appropriate.

---

## Modularity

Prefer:

```text
Small focused modules
```

over:

```text
Large multipurpose files
```

---

Example:

Good:

```text
services/
  rxnorm.py
  dailymed.py
  openfda.py
```

Bad:

```text
api_helpers.py
```

containing everything.

---

## Explicit Naming

Prefer:

```python
fetch_drug_recalls()
```

over:

```python
get_data()
```

Function names should communicate intent.

---

## Error Handling

External APIs will fail.

Handle:

* Network failures
* Rate limits
* Missing fields
* Empty results
* Invalid responses

Never assume API success.

---

# Evaluation Requirements

Every major feature should have a validation strategy.

Ask:

```text
How do we know this works?
```

before implementing.

---

Examples:

Drug Investigation:

* Does RxNorm return the correct generic name?

Recall Retrieval:

* Does FDA data match known recall records?

Report Generation:

* Are critical findings preserved?

Evaluation should be considered during implementation, not afterward.

---

# Feature Requests

When a new feature is requested:

Evaluate it against the following questions.

---

## Question 1

Does this align with the project's purpose?

If not:

Recommend against implementation.

---

## Question 2

Does this introduce unnecessary complexity?

If yes:

Suggest a simpler alternative.

---

## Question 3

Can this be solved with deterministic software?

If yes:

Do not immediately use Gemini.

---

## Question 4

Does this belong in Version 1?

If not:

Recommend placing it in Future Enhancements.

---

# Performance Principles

Prefer:

```text
Simple
Reliable
Observable
```

over:

```text
Clever
Complex
Agentic
```

---

A system that is:

```text
90% as intelligent
```

but

```text
5x easier to debug
```

is usually the better engineering choice.

---

# Preferred Workflow Pattern

The preferred pattern throughout the project is:

```text
User Query
↓
Gemini Intent Router
↓
Predefined Workflow
↓
Evidence Collection
↓
Evidence Aggregation
↓
Gemini Analysis
↓
Response
```

When proposing new features, try to fit them into this pattern.

---

# If Unsure

When uncertain about an implementation decision, ask:

```text
Should this responsibility belong to Gemini or deterministic software?
```

Use the following rule:

Reasoning → Gemini

Execution → Software

This principle should guide all future development decisions.
