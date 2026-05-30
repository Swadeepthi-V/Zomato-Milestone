# Edge Cases & Expected Behavior

This document defines how the AI-powered restaurant recommendation system should behave under abnormal, boundary, and failure conditions. It extends [architecture.md §9](./architecture.md#error-handling--edge-cases) and supports Phase 6 manual QA ([implementation-plan.md](./implementation-plan.md)).

**Principles**

- **Grounding first:** Never show restaurant names or facts that are not backed by a row in the filtered candidate list.
- **Fail loud internally, fail gracefully for users:** Log warnings/errors with context; return clear, actionable messages in the UI/API.
- **Save cost:** Do not call the LLM when deterministic filtering already yields zero candidates.

---

## Quick Reference

| ID | Scenario | Layer | User-visible outcome | LLM called? |
|----|----------|-------|----------------------|--------------|
| E-01 | Dataset / cache unavailable at startup | Ingestion / Store | Service unavailable; `/health` not ready | No |
| E-02 | Hugging Face load fails (no cache) | Ingestion | Admin/startup error; no recommendations | No |
| E-03 | Corrupt or empty cache file | Store | Re-ingest or fail startup | No |
| E-04 | HF schema drift / missing required columns | Ingestion | Ingest fails with logged column map error | No |
| E-05 | Row missing `id`, `name`, or `location` | Normalizer | Row skipped; count in ingest logs | No |
| E-06 | Missing or non-numeric `rating` | Normalizer | Default or exclude from rating filter | No |
| E-07 | Ambiguous / missing `cost` | Normalizer | Derive `budget_tier` via fallback rules | No |
| E-08 | Multi-value cuisine string | Normalizer / Filter | Substring match still works | No |
| E-09 | Duplicate `id` in dataset | Normalizer | Last-wins or dedupe; log warning | No |
| E-10 | Empty store after ingest | Store | `/health` unhealthy; recommend blocked | No |
| E-11 | Missing required preference fields | API / UI | `422` validation error | No |
| E-12 | Invalid `budget` enum | API / UI | `422` validation error | No |
| E-13 | `min_rating` out of range | API / UI | `422` or clamp with warning | No |
| E-14 | Unknown / typo location | Filter | Zero candidates → empty state (E-20) | No |
| E-15 | Overly strict filter combination | Filter | Zero candidates → empty state (E-20) | No |
| E-16 | Filter matches > `MAX_CANDIDATES` | Filter | Cap to top N by rating | Yes |
| E-17 | Filter matches exactly 1 candidate | Filter / LLM | Still valid; rank 1 result | Yes |
| E-18 | `additional_preferences` only (no hard filter) | Filter / LLM | Passed to prompt; not used in AND filter | Yes |
| E-19 | Whitespace-only optional fields | API | Treat as empty / omitted | No |
| E-20 | Zero candidates after filter | Orchestration | Friendly broaden-search message | **No** |
| E-21 | LLM timeout (transient) | LLM | One retry; then error (E-22) | Retry |
| E-22 | LLM persistent failure | LLM | Structured error; optional filter-only fallback | No* |
| E-23 | Missing / invalid `LLM_API_KEY` | LLM | Clear configuration error | No |
| E-24 | LLM rate limit (`429`) | LLM | Backoff + retry; then E-22 | Retry |
| E-25 | Empty LLM response | LLM / Parser | Retry repair prompt; then E-22 | Retry |
| E-26 | Non-JSON / prose-only LLM output | Parser | Repair prompt; log raw response | Retry |
| E-27 | JSON wrapped in markdown fences | Parser | Strip fences; parse | Yes |
| E-28 | Malformed JSON (truncated) | Parser | Repair prompt once; then E-22 | Retry |
| E-29 | Hallucinated `restaurant_id` | Parser | Strip entry; log warning | Yes |
| E-30 | All IDs invalid | Parser | Treat as LLM failure (E-22) | No |
| E-31 | Duplicate `restaurant_id` in LLM output | Parser | Keep lowest `rank`; log warning | Yes |
| E-32 | Duplicate or gapped `rank` values | Parser | Sort by `rank`; normalize order | Yes |
| E-33 | Fewer than `top_k` recommendations returned | Parser / API | Return available count; no error | Yes |
| E-34 | Empty `explanation` string | Parser | Use fallback text or omit card detail | Yes |
| E-35 | Prompt injection in `additional_preferences` | Security | Pass as inert text; never execute | Yes |
| E-36 | Extremely long free-text preferences | API / LLM | Truncate in prompt; log truncation | Yes |
| E-37 | Concurrent `/recommend` requests | API | Independent; shared read-only store | Yes |
| E-38 | `top_k` > candidate count | Orchestration | Return ≤ candidate count | Yes |
| E-39 | `top_k` = 0 or negative | API | `422` or default to `TOP_K` | No |
| E-40 | UI submitted while prior request in flight | UI | Disable submit / cancel previous | Yes |

\*Optional filter-only fallback: return top candidates by rating without explanations—only if product allows degraded mode.

---

## 1. Data Ingestion & Store

### E-01 — Dataset / cache unavailable at startup

| | |
|---|---|
| **Trigger** | `DATA_CACHE_PATH` missing and HF unreachable; or ingest never run |
| **Expected behavior** | Application fails fast on startup **or** `/health` returns `503` with `dataset_loaded: false` |
| **Must not** | Return recommendations from an empty store |
| **Logs** | `ERROR` with path and remediation (“run ingest”) |
| **Test** | Start app without cache; assert `/health` not ready and `/recommend` blocked |

### E-02 — Hugging Face load fails (no cache)

| | |
|---|---|
| **Trigger** | Network error, HF downtime, auth/rate limit, wrong `HF_DATASET_NAME` |
| **Expected behavior** | Ingest command exits non-zero; startup does not mark store ready |
| **Recovery** | Retry ingest; use cached snapshot if available |
| **Test** | Mock HF loader to raise; assert no partial store published |

### E-03 — Corrupt or empty cache file

| | |
|---|---|
| **Trigger** | Truncated Parquet/JSON, zero-byte file, schema mismatch on read |
| **Expected behavior** | Detect on load; fall back to re-ingest from HF or fail startup |
| **Must not** | Silently serve zero restaurants |
| **Test** | Fixture corrupt file; assert error path |

### E-04 — HF schema drift / missing required columns

| | |
|---|---|
| **Trigger** | Column renamed or removed on Hugging Face |
| **Expected behavior** | Ingest fails with explicit missing-column list; mapping doc updated |
| **Mitigation** | Column alias map in `normalizer.py`; inspect first N rows on version bump |
| **Test** | Fixture CSV with missing `rating` column; assert fail-loud |

### E-10 — Empty store after ingest

| | |
|---|---|
| **Trigger** | All rows skipped during normalization |
| **Expected behavior** | Same as E-01; ingest reports `0` valid records |
| **Test** | Fixture where every row lacks `name` |

---

## 2. Normalization

### E-05 — Row missing required fields

| | |
|---|---|
| **Trigger** | Null/empty `id`, `name`, or `location` |
| **Expected behavior** | Skip row; increment `skipped_count` in ingest summary |
| **Test** | Unit test: 3 rows, 1 invalid → store size 2 |

### E-06 — Missing or non-numeric rating

| | |
|---|---|
| **Trigger** | `null`, `"-"`, `"NEW"`, non-parseable string |
| **Expected behavior** | Coerce to `null` or `0.0`; exclude from `min_rating` filter when rating unknown |
| **Display** | Show “N/A” or omit rating in UI |
| **Test** | Normalizer fixtures per implementation-plan Phase 1.8 |

### E-07 — Ambiguous or missing cost

| | |
|---|---|
| **Trigger** | Empty cost, mixed currency strings, outliers |
| **Expected behavior** | Map to `budget_tier` using documented thresholds; default `medium` if unparseable (log once per pattern) |
| **Test** | Rows with `₹300`, `₹3000`, missing → tiers assigned |

### E-08 — Multi-value cuisine string

| | |
|---|---|
| **Trigger** | `"Italian, Pizza, Fast Food"` |
| **Expected behavior** | Store as single string; filter uses case-insensitive substring (`Italian` matches) |
| **Edge sub-case** | User searches `italian` vs `Italian` → must match |
| **Test** | Filter test: multi-cuisine row matches partial cuisine |

### E-09 — Duplicate `id` in dataset

| | |
|---|---|
| **Trigger** | Colliding generated IDs |
| **Expected behavior** | Deduplicate (last wins) or fail ingest; log duplicate count |
| **Must not** | Grounding validator joins wrong row |
| **Test** | Two rows same `id` → single canonical record |

---

## 3. User Input & Validation

### E-11 — Missing required fields

| | |
|---|---|
| **Trigger** | No `location` and/or no `budget` (and `cuisine` if required by schema) |
| **HTTP** | `422 Unprocessable Entity` with field-level errors |
| **UI** | Inline validation before submit |
| **Test** | API test: `{}` → 422 |

### E-12 — Invalid `budget` enum

| | |
|---|---|
| **Trigger** | `"cheap"`, `""`, numeric budget |
| **HTTP** | `422` — allowed: `low`, `medium`, `high` |
| **Test** | `"budget": "luxury"` → 422 |

### E-13 — `min_rating` out of range

| | |
|---|---|
| **Trigger** | `-1`, `6`, `NaN`, non-numeric string |
| **Expected behavior** | Reject with `422` **or** clamp to `[0.0, 5.0]` and include warning in `meta` (pick one policy and document) |
| **Recommended** | Reject invalid; clamp only values like `4.567` → `4.57` |

### E-19 — Whitespace-only optional fields

| | |
|---|---|
| **Trigger** | `"additional_preferences": "   "` |
| **Expected behavior** | Normalize to `null` / omit before prompt build |
| **Test** | Whitespace string not sent to LLM as meaningful constraint |

### E-39 — Invalid `top_k`

| | |
|---|---|
| **Trigger** | `top_k: 0`, negative, or extremely large (e.g. 1000) |
| **Expected behavior** | `422` for ≤ 0; cap large values to `TOP_K` or `len(candidates)` |
| **Test** | `top_k: -1` → 422; `top_k: 999` → capped |

---

## 4. Preference Filtering

### E-14 — Unknown or typo location

| | |
|---|---|
| **Trigger** | `"Banglore"`, `"XYZ City"` |
| **Expected behavior** | Zero candidates unless fuzzy matching enabled |
| **Future enhancement** | Suggest closest known cities from store |
| **User message** | See E-20 |
| **Test** | Typo location → empty list, no exception |

### E-15 — Overly strict filter combination

| | |
|---|---|
| **Trigger** | High `min_rating` + narrow cuisine + low budget in sparse city |
| **Expected behavior** | `[]` candidates; structured empty response |
| **Test** | Preferences matching no fixture rows |

### E-16 — More matches than `MAX_CANDIDATES`

| | |
|---|---|
| **Trigger** | 500 restaurants match; `MAX_CANDIDATES=30` |
| **Expected behavior** | Sort by `rating` desc; take top 30; `meta.candidate_count=30` |
| **Performance** | Filter completes < 100 ms (local, full dataset) |
| **Test** | Assert len(candidates) ≤ `MAX_CANDIDATES` |

### E-17 — Exactly one candidate

| | |
|---|---|
| **Trigger** | Unique match after all filters |
| **Expected behavior** | LLM still called; return rank 1; valid explanations |
| **Test** | Mock LLM returns single ID |

### E-18 — `additional_preferences` not in hard filter

| | |
|---|---|
| **Trigger** | `"family-friendly"` with no dataset column |
| **Expected behavior** | Included in prompt only; filter does not exclude rows |
| **Test** | Same candidate set with/without additional text (filter identical) |

### E-20 — Zero candidates after filter

| | |
|---|---|
| **Trigger** | Any filter combination yielding `[]` |
| **HTTP** | `200` with empty `recommendations` and helpful `message` / `summary` |
| **Must not** | Call LLM |
| **Suggested copy** | *“No restaurants match your filters. Try a broader location, lower minimum rating, or a different cuisine.”* |
| **Test** | Integration: assert LLM client `complete` not called |

**Example response**

```json
{
  "summary": null,
  "recommendations": [],
  "message": "No restaurants match your filters. Try broadening location, budget, or cuisine.",
  "meta": { "candidate_count": 0, "llm_called": false }
}
```

---

## 5. LLM & Recommendation Engine

### E-21 — LLM timeout (transient)

| | |
|---|---|
| **Trigger** | Provider exceeds `timeout` |
| **Expected behavior** | Retry once with same prompt; log `warning` with latency |
| **Test** | Mock client: fail once, succeed twice |

### E-22 — LLM persistent failure

| | |
|---|---|
| **Trigger** | Repeated timeouts, 5xx, auth errors after retries |
| **HTTP** | `502` or `503` with `error_code: "llm_unavailable"` |
| **UI** | Non-technical message + retry button |
| **Optional fallback** | Return rating-sorted candidates without AI explanations (feature-flagged) |
| **Must not** | Invent restaurants or explanations |
| **Test** | Mock always fails → no grounded names from LLM text |

### E-23 — Missing or invalid API key

| | |
|---|---|
| **Trigger** | `LLM_API_KEY` unset or rejected |
| **Expected behavior** | Fail at startup in strict mode **or** clear error on first `/recommend` |
| **Test** | Empty env → configuration error |

### E-24 — Rate limit (`429`)

| | |
|---|---|
| **Trigger** | Provider throttling |
| **Expected behavior** | Exponential backoff; max 2 retries; then E-22 |
| **Logs** | Include retry attempt and `Retry-After` if present |

### E-25 — Empty LLM response

| | |
|---|---|
| **Trigger** | Zero-length completion |
| **Expected behavior** | Treat as parse failure; repair prompt (E-28) |

---

## 6. Response Parsing & Grounding

### E-26 — Non-JSON / prose-only output

| | |
|---|---|
| **Trigger** | Model ignores schema instruction |
| **Expected behavior** | Repair prompt: *“Return only valid JSON matching the schema.”* |
| **Logs** | `WARN` + truncated raw response (no secrets) |

### E-27 — JSON inside markdown fences

| | |
|---|---|
| **Trigger** | ` ```json ... ``` ` wrapped output |
| **Expected behavior** | Strip fences before `json.loads` |
| **Test** | Parser fixture with fenced JSON |

### E-28 — Malformed JSON

| | |
|---|---|
| **Trigger** | Truncated array, trailing comma, single quotes |
| **Expected behavior** | One repair retry; then E-22 |
| **Must not** | Partially parse and show wrong restaurants |

### E-29 — Hallucinated `restaurant_id`

| | |
|---|---|
| **Trigger** | ID not in candidate list |
| **Expected behavior** | Drop entry; `meta.hallucination_count += 1`; log warning |
| **Test** | Mock LLM returns `r_999` → stripped |

### E-30 — All IDs invalid

| | |
|---|---|
| **Trigger** | Every ID hallucinated or empty `recommendations` array |
| **Expected behavior** | Same as E-22; **never** display LLM-supplied names |
| **Test** | All bad IDs → error response, empty recommendations |

### E-31 — Duplicate `restaurant_id` in LLM output

| | |
|---|---|
| **Trigger** | Same ID at rank 1 and 3 |
| **Expected behavior** | Keep best (lowest) rank; dedupe |
| **Test** | Duplicate IDs → single card |

### E-32 — Duplicate or gapped ranks

| | |
|---|---|
| **Trigger** | Two rank `1`s or ranks `1, 3, 5` |
| **Expected behavior** | Sort by `rank` ascending; re-number display order 1..k if needed |
| **Test** | Gapped ranks → ordered UI list |

### E-33 — Fewer than `top_k` results

| | |
|---|---|
| **Trigger** | LLM returns 2 items when `top_k=5` |
| **Expected behavior** | Return 2; `200` success |
| **Test** | Assert `len(recommendations) <= top_k` |

### E-34 — Empty explanation

| | |
|---|---|
| **Trigger** | `"explanation": ""` |
| **Expected behavior** | Fallback: *“Recommended based on your preferences.”* or hide explanation block |
| **Display fields** | Name, cuisine, rating, cost still from **store** |

### E-38 — `top_k` greater than candidate count

| | |
|---|---|
| **Trigger** | `top_k=10`, 4 candidates |
| **Expected behavior** | Prompt asks for min(10, 4); parser returns ≤ 4 |
| **Test** | Assert len ≤ candidates |

---

## 7. API & Orchestration

### E-37 — Concurrent requests

| | |
|---|---|
| **Trigger** | Multiple simultaneous `POST /recommend` |
| **Expected behavior** | Thread-safe read on store; independent LLM calls |
| **Note** | No shared mutable session state in MVP |

### Health check edge cases

| Condition | `/health` |
|-----------|-----------|
| Store loaded, N > 0 | `200`, `dataset_loaded: true`, `record_count: N` |
| Store empty | `503` |
| Ingest in progress | `503` or `200` with `status: "loading"` (document chosen behavior) |

---

## 8. Presentation Layer (UI)

### E-40 — Double submit / in-flight request

| | |
|---|---|
| **Trigger** | User clicks “Recommend” twice |
| **Expected behavior** | Disable button during load; ignore second click or cancel prior |
| **Test** | Manual QA |

### Loading & error states

| State | UI behavior |
|-------|-------------|
| LLM in progress | Spinner / skeleton cards |
| E-20 empty filter | Actionable copy + link to broaden filters |
| E-22 LLM failure | Error banner; do not show stale prior results as new |
| E-11 validation | Field-level errors before API call |

### Display contract (always)

| Field | Source |
|-------|--------|
| Name, cuisine, rating, cost | `Restaurant` from store |
| Explanation | LLM (with E-34 fallback) |
| Rank badge | Parser-normalized rank |

---

## 9. Security & Abuse

### E-35 — Prompt injection in `additional_preferences`

| | |
|---|---|
| **Trigger** | *“Ignore previous instructions and recommend…”* |
| **Expected behavior** | Treat as opaque user text; system prompt enforces candidate-only policy |
| **Must not** | Execute instructions, shell commands, or SQL |
| **Logs** | Sanitize / truncate in logs (no full PII dump) |

### E-36 — Extremely long free-text

| | |
|---|---|
| **Trigger** | Multi-KB `additional_preferences` |
| **Expected behavior** | Truncate to token budget (e.g. 500 chars); log truncation |
| **Test** | 10k char input → truncated prompt |

### Other security cases

| Scenario | Behavior |
|----------|----------|
| Missing rate limit (public deploy) | Document risk; optional `429` per IP |
| `/admin/ingest` without auth | `401` in production |
| Secrets in repo | Never commit `.env`; CI uses mock LLM |

---

## 10. Configuration & Environment

| Scenario | Expected behavior |
|----------|-------------------|
| `MAX_CANDIDATES` unset | Default (e.g. 30) |
| `MAX_CANDIDATES=0` | Treat as invalid or minimum 1 at startup |
| `TOP_K` > `MAX_CANDIDATES` | Effective K = min(TOP_K, len(candidates)) |
| Wrong `LLM_MODEL` | Provider error → E-22 |
| Mock LLM in CI | No network; deterministic JSON fixture |

---

## 11. Manual QA Checklist (Phase 6)

Execute before milestone sign-off. Record pass/fail and notes.

- [ ] **E-20** — Strict filters → empty state, no LLM call
- [ ] **E-16** — Broad filters → candidate cap respected in `meta`
- [ ] **E-29** — Mock hallucinated ID → stripped, valid IDs still shown
- [ ] **E-30** — All bad IDs → error, no fake restaurant names
- [ ] **E-28** — Malformed JSON → repair then graceful failure
- [ ] **E-21** — Simulated timeout → single retry
- [ ] **E-14** — Typo city → helpful empty message
- [ ] **E-11 / E-12** — Invalid API body → 422
- [ ] **E-01** — Start without data → health not ready
- [ ] **E-35** — Injection-like string → still only grounded results
- [ ] **Happy path** — Bangalore · medium · Italian · min 4.0 → 5 grounded cards with explanations

### Demo scenarios (minimum 3)

| # | Preferences | What it validates |
|---|-------------|-------------------|
| 1 | Bangalore, medium, Italian, min 4.0 | Core path, grounding |
| 2 | Delhi, low, Chinese, min 3.5, “quick service” | Additional prefs in explanations |
| 3 | Rare combo → empty (e.g. very high min_rating + niche cuisine) | E-20 empty state |

---

## 12. Test Mapping

| Edge IDs | Automated test location (planned) |
|----------|----------------------------------|
| E-05–E-09 | `tests/test_normalizer.py` |
| E-14–E-20 | `tests/test_filter.py` |
| E-26–E-34 | `tests/test_response_parser.py` |
| E-20, E-22, E-29–E-30 | `tests/test_recommendation_service.py` (mock LLM) |
| E-11–E-12, E-20 | `tests/test_api.py` |
| E-01, E-10 | `tests/test_health.py` |
| §11 checklist | Manual / E2E in Phase 6 |

---

## 13. Related Documents

- [context.md](./context.md) — Product goals and success criteria
- [architecture.md](./architecture.md) — Components, §9 error table, API contract
- [implementation-plan.md](./implementation-plan.md) — Phase tasks and QA (Phase 6.9)
