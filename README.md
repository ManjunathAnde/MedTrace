#📑 MedTrace

**AI that proves every answer, built for the highest-stakes case: medication safety.**

[Live app](https://med-trace-liart.vercel.app) | [LinkedIn](https://www.linkedin.com/in/manjunath-ande/)

MedTrace answers medication questions for **pharmacists and clinicians** using only public FDA data. Every claim it shows is checked in code against the exact FDA passage it cites. Claims that fail the check are removed, and the user sees what was removed and why.

> **LLM for judgment. Code for guarantees.**
> The LLM writes and judges. Deterministic code fetches the data, checks every quote, sets severity and status, and decides what reaches the user. No LLM output reaches the user without a code check behind it.

---

## Why MedTrace?

LLMs are good at writing fluent answers and bad at proving them. Telling a model "only use FDA sources" is a request, not a guarantee.

MedTrace enforces sources instead of asking for them:

- Every claim carries an evidence ID, a verbatim quote from the label, a link to the label, and its effective date.
- A **citation verifier** checks each claim before it's shown.
- When the verifier can't prove a claim, it cuts it. When in doubt, it fails closed.

---

## Features

### 1. Ask MedTrace (`POST /investigate`)
One-drug questions: boxed warnings, contraindications, warnings, dosing, indications.

Returns a list of short claims. Each claim has a source tag that opens the exact label passage with the quote highlighted. The UI shows **"Claims verified: X of Y"** and which label was used.

### 2. Prescription Check (`POST /prescription-check`)
Takes 2 to 5 medications. For each pair, it:

1. Searches each FDA label in code for the other drug's names (no LLM call if neither label names the other).
2. If found, runs the interaction agent to write claims from the label text.
3. Verifies every claim.
4. Assigns severity (High / Moderate / Info) with code rules, not the LLM.
5. Lists FDA recalls by ingredient.


### 3. Citation Verifier
The verifier knows nothing about drugs. It only sees claims and passages, and it imports nothing from the drug modules. Swap FDA labels for contracts, regulations, or financial filings and the same verifier works.

| Layer | Type | Check | Cut code |
| --- | --- | --- | --- |
| L0 | code | The cited evidence ID exists | `CUT_BAD_ID` |
| L1 | code | The quote is 5 to 30 words and appears **verbatim** in the cited passage (after normalizing case, quotes, dashes, whitespace) | `CUT_QUOTE` |
| L2 | LLM | Does the passage support the claim as written? | `CUT_SUPPORT` |
| L3 | code | No directive language ("you should", "stop taking", ...) | `CUT_DIRECTIVE` |

**L1 is the hard guarantee.** A quote either is in the passage or it isn't, and no model can talk its way past a substring check. L2 is an LLM and can be wrong, which is why removed claims are shown, not hidden.

---

## Architecture

```text
Browser (Vercel, React)
   |  POST /investigate  or  POST /prescription-check
   v
FastAPI (Render)
   |-- safety walls, extraction, intent        (LLM helpers + code guards)
   |-- RxNorm, DailyMed, openFDA, recalls      (deterministic API tools)
   |-- evidence store                          (code: numbered passages E1..En)
   |-- synthesizer / interaction agent         (LLM agents: write claims)
   |-- citation verifier                       (code checks + one LLM support check)
   |-- severity + status rules                 (code)
   |-- Upstash Redis cache                     (code)
   v
JSON response -> UI cards with source tags
```

### Agents vs tools

| Kind | Members | Job |
| --- | --- | --- |
| LLM agents | synthesizer, interaction agent, verifier support check | Write claims; judge whether a passage supports a claim |
| LLM helpers | safety classifier, extractor, intent classifier | Classify and extract |
| Deterministic tools | RxNorm, DailyMed, openFDA, FAERS, recalls, evidence store, guards, verifier L0/L1/L3, severity rules, status rules, cache | Everything that must be guaranteed |

Orchestration is plain async Python. Code decides which sources get called and in what order. The LLM never plans tool calls. **Specialized agents in a controlled pipeline: predictable over autonomous, because it's medication safety.**


## Design decisions

**Safety in three walls.** Regex rules catch self-harm and personal-advice phrasing. An LLM classifier handles the rest. Interaction questions about named drugs stay allowed ("Can I take ibuprofen with lisinopril?" is SAFE; "Can I take my wife's lisinopril?" is PERSONAL_ADVICE). The verifier's L3 layer removes any directive language from claims.

**Extraction is guarded in code.** The LLM copies drug names exactly as typed. Code keeps a name only if it actually appears in the user's text.

**RxNorm is exact, not fuzzy.** Typos return NOT_RECOGNIZED instead of guessing. RxNorm is a hard dependency: if it's down, the request returns HTTP 503, because a wrong drug identity makes everything after it meaningless.

**The label used is always shown.** Label selection uses ordered tie-breakers, and the UI shows the chosen label's title, set ID and effective date.

**Severity is code, with negation handling.** High / Moderate / Info come from phrases in the cited passages and from which label section they're in. No-effect statements ("no dose adjustment", "no clinically significant interaction") are masked before matching, so they don't trigger a false signal.

**Honest statuses.** Every expected outcome returns HTTP 200 with a `status` field:

| Status | Meaning |
| --- | --- |
| `ANSWERED` | All claims kept, no gaps |
| `PARTIAL` | Some claims cut or gaps reported |
| `INSUFFICIENT_EVIDENCE` | Nothing survived, or the evidence can't answer the question |
| `BLOCKED` | Personal advice or self-harm |
| `UNAVAILABLE` | Both LLM providers failed |
| `NO_DRUG` / `NOT_RECOGNIZED` | No drug named / RxNorm didn't recognize it |
| `REDIRECT` / `ONE_AT_A_TIME` | Multi-drug questions in Ask |
| `COMPLETE` / `TOO_FEW` / `TOO_MANY` | Prescription Check outcomes |

### LLM providers and failover

Every LLM call tries **Gemini first, then Groq**. Responses are temperature 0, structured JSON validated against Pydantic schemas, with an explicit token budget per call.

| Provider | Model |
| --- | --- |
| Gemini (first) | `gemini-2.5-flash-lite` |
| Groq (fallback) | `qwen/qwen3.8-27b` |

Groq retry rules: a per-minute rate limit waits and retries once; a daily limit fails immediately; a 5xx, timeout or connection error waits 2 seconds and retries once. If both providers fail, the status is `UNAVAILABLE`, never `BLOCKED`.

### Failure strategy

| Component | If it fails |
| --- | --- |
| RxNorm | Critical: HTTP 503 |
| DailyMed, openFDA, recalls, FAERS | Degrade: continue and record the gap |
| Both LLM providers | Status `UNAVAILABLE` |
| Cache (Upstash Redis) | Never blocks a request; the pipeline just runs |

### Caching

Upstash Redis lives outside the app process, so cached answers survive Render free-tier cold starts.

| What | TTL | Stored when |
| --- | --- | --- |
| Ask, warnings questions | 30 days | `ANSWERED` or `PARTIAL` |
| Ask, other questions | 12 hours | `ANSWERED` or `PARTIAL` |
| Prescription Check | 12 hours | `COMPLETE` |

---

---

## Tech stack

**Backend:** Python 3.13, FastAPI, Pydantic v2, httpx, async Python
**Frontend:** React, TypeScript, Vite, Tailwind CSS
**AI:** Google Gemini, Groq (fallback)
**Data sources:** RxNorm, DailyMed, openFDA (labels, FAERS, enforcement/recalls)
**Cache:** Upstash Redis
**Hosting:** Render (backend), Vercel (frontend)

---

## Running locally

Backend:

```bash
git clone https://github.com/ManjunathAnde/MedTrace.git
cd MedTrace
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Environment variables:

```text
GOOGLE_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite
GROQ_API_KEY=
GROQ_MODEL=qwen/qwen3.8-27b
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
```

Frontend:

```bash
cd frontend/MedIntel-FE
npm install
npm run dev          # real mode, proxies to localhost:8000
npm run dev:mocks    # mock mode, saved real responses, no backend needed
```

---

## Disclaimer

MedTrace shows FDA drug label information for pharmacists and clinicians. It is not medical advice and is not a substitute for professional clinical judgment.
