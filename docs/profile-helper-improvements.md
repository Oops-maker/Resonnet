# Profile Helper: Behavioral Assessment Upgrade & Architecture Improvements

## Overview

This document covers a series of improvements to the Profile Helper system,
focusing on three areas:

1. **Scientific rigor** — AI memory extraction is now grounded in validated
   psycholinguistic research (LIWC meta-analysis, SDT linguistic markers,
   Integrative Complexity coding).
2. **Reliability** — Profile data integrity is enforced at the tool layer;
   caching eliminates redundant LLM calls; conversation analytics enable
   systematic debugging.
3. **Architecture** — Session reset semantics are clarified; server-side
   export decouples rendering from the browser; sync to `digital_twins` enables
   cross-device profile persistence.

---

## 1. AI Memory Extraction Prompt v2.1

**File:** `libs/profile_helper/prompts/ai-memory-v2.md`

The prompt sent to external AI platforms (ChatGPT, Claude, Gemini) has been
redesigned from the ground up. Instead of asking the AI to summarize the user's
personality directly, it now requests structured **behavioral observations**
across seven modules (A–G), grounded in validated psychological frameworks:

| Module | Purpose | Theoretical Basis |
|--------|---------|-------------------|
| A | Basic identity (research stage, field, institution) | Factual |
| B | Research capabilities and outputs | Factual |
| C | Current needs and pain points | Situational self-report |
| D | Cognitive style signals (5 indicators) | AHS (Choi et al., 2007); Integrative Complexity (Baker-Brown et al., 1992) |
| E | Academic motivation signals (7 indicators) | AMS / SDT (Vallerand et al., 1992; Ryan & Deci, 2017) |
| F | Personality signals (6 indicators) | LIWC meta-analysis (Koutsoumpis et al., 2022, n = 85,724) |
| G | Learning style and work habits | Behavioral self-report |

Each question specifies:
- What behavior to look for (not "what is the user's personality")
- Reference language patterns (with ✅/⚠️/❌ confidence labels)
- The psychological construct it corresponds to

The prompt ends with a mandatory completeness declaration and an optional
inference-mapping table so the consuming system can do structured extraction.

---

## 2. Import-AI-Memory-v2 Skill: Evidence-Based Inference

**File:** `libs/profile_helper/skills/import-ai-memory-v2/SKILL.md`

Step 2 of the import skill has been rewritten to use a **pre-extraction +
mapping-table** approach instead of free-form LLM reasoning:

### RCSS (Cognitive Style) Mapping

Before estimating each of the 8 RCSS items (1–7 scale), the LLM first
extracts D1–D5 behavioral signals from the pasted AI response:

| RCSS Item | Primary Evidence | Fallback |
|-----------|-----------------|---------|
| A1 Cross-domain inspiration | D3 cross-domain connection behavior | Diverse tech stack |
| A2 Broad theoretical frameworks | D1 multi-factor causal reasoning + D3 | Computational/data-driven method |
| B1 Vertical depth preference | D3 absent + D4 detail-first focus | Experimental/theoretical method |

### AMS (Academic Motivation) Mapping

Each of the 7 AMS dimensions is mapped to a specific E-module signal with
explicit scoring rules:

| AMS Dimension | Signal | Rule |
|---------------|--------|------|
| IM-know | E1: spontaneous topic introduction | Frequent ✅ → 6–7; occasional ⚠️ → 4–5; ❌ → 3 |
| Amotivation | E7: meaninglessness expression | ✅ verbatim → 5–7 + risk flag in interpretation |

### Big Five Mapping

F-module signals are mapped to OCEAN dimensions with LIWC effect-size
annotations (all rated "low confidence" per the meta-analytic evidence):

| Dimension | Signal | Effect Size |
|-----------|--------|-------------|
| Emotional Stability | F1: 1st-person singular pronoun freq. + negative affect | ρ = −.29 (strongest) |
| Conscientiousness | F2: neutral language + F5: work system | ρ = −.10–.12 |
| Agreeableness | F2: anger words + F3: how user talks about others | ρ = −.14 |

---

## 3. Profile Format Validation

**File:** `app/services/profile_helper/block_agent.py` → `_execute_backend_tool`

`write_profile` now validates the markdown format before saving. If the content
does not match the expected template structure, it returns an explicit error
and instructs the LLM to call `read_profile()` first:

```
Required: first line matches /^# 科研人员画像/
Required sections: ## 一、基础身份 / ## 二、能力 / ## 三、当前需求
```

This prevents a class of bugs where the LLM writes in a self-invented format
(e.g., `# 科研数字分身 / ## 第一章`) that the profile parser cannot parse,
resulting in an empty profile page for the user.

---

## 4. Two-Level Scientist Match Cache

**File:** `app/services/profile_helper/scientist_match.py`

Two new cached wrappers eliminate redundant LLM calls on every page load:

### `get_cached_match(session, parsed)` — Famous Scientist Match

- **Level 1**: In-memory session cache (`session["_scientist_cache"]`)
- **Level 2**: Filesystem cache (`workspace/.../scientist_cache.json`)
- **Cache key**: SHA-256 of raw profile markdown content
- **Empty profile guard**: Skips the personalized-reason LLM call if the
  profile has no CSI/RAI data yet

### `get_cached_field_recommendations(session, parsed)` — Field Recommendations

Same two-level caching strategy applied to the LLM-based field scientist
recommendations (previously called on every page load with no caching).

**Impact**: After the first visit to the profile page, subsequent loads of
`/scientists/field` return in < 1 ms (memory cache hit) rather than 5–15 s
(LLM call).

---

## 5. Conversation Analytics Logger (new file)

**File:** `app/services/profile_helper/conversation_logger.py`

An append-only JSONL logger that records the complete interaction trace for
every session — independent of session resets, cleanup, or profile rewrites.

**Log location**: `workspace/profile_helper/logs/sessions/{session_id}.jsonl`

**Recorded events**:

| Event Type | Description |
|-----------|-------------|
| `user_message` | Everything the user types/pastes |
| `assistant_text` | AI text responses |
| `ui_block` | Every UI element shown (choice, text_input, rating, actions) with full option lists |
| `tool_call` | Every LLM tool call (read_skill, write_profile, ask_choice, …) with arguments |
| `tool_result` | Result of each tool call (truncated to 500 chars, full length recorded) |
| `llm_call` | LLM API invocation metadata (model, message count) |
| `llm_response` | LLM response metadata (has tool calls, text length) |
| `fast_path` | Fast-path triggers (welcome, ai_memory_prompt, …) |
| `error` | Any error during processing |

Each entry includes `ts` (UTC ISO-8601), `session_id`, and `user_id`
(null for anonymous sessions).

---

## 6. Server-Side Profile Export (new file)

**File:** `app/services/profile_helper/export_service.py`

**New API endpoints**: `GET /profile-helper/export/{session_id}/pdf`  
and `GET /profile-helper/export/{session_id}/image`

The export service converts `profile.md` to a styled HTML document and
renders it to PDF or PNG using a headless browser (Edge/Chromium), bypassing
the browser's print dialog entirely.

### Export Pipeline

```
profile.md
  └─ parse_profile()           → structured dict
       ├─ get_cached_match()   → top-3 scientists (from cache)
       ├─ get_cached_field_recommendations() → field recs (from cache)
       └─ render_profile_html() → full HTML with:
            · Brand CSS (Noto Serif SC, black/white minimal)
            · Score bars for AMS / Big Five dimensions
            · CSI track for RCSS
            · Inline SVG scatter chart (CSI × RAI)
            · Scientist cards (top-3 + field recommendations)
            └─ Edge headless
                 ├─ --print-to-pdf  → profile.pdf
                 └─ --screenshot (tiled) → profile.png
```

The service uses session cache for scientist data, so export does not trigger
additional LLM calls if the profile page has already been viewed.

---

## 7. Session Architecture Improvements

**File:** `app/services/profile_helper/sessions.py`

### `reset_conversation_only(session_id)`

New reset semantics that match user expectations for "start a new build":

- ✅ Clears in-memory messages
- ✅ Deletes `messages.json` from disk
- ✅ Resets profile in session memory to blank template
- ✅ Clears scientist cache
- ❌ Does NOT delete `profile.md` from disk
- ❌ Does NOT touch `digital_twins` records

Previously, `reset()` only cleared in-memory state without touching disk,
causing the session to restore stale data on the next `get_or_create`.

### Token-Aware `get_or_create()`

`get_or_create` now accepts and stores the auth token in the session dict,
enabling `save_profile` to call `_sync_profile_to_digital_twins()` for
logged-in users — persisting the profile to `topiclab-backend` after every
write, so profiles survive Resonnet restarts.

### `_pull_profile_from_digital_twins(user_id)`

When rebuilding a session for a logged-in user whose local `profile.md` is
missing, the system attempts to pull the last-known profile from
`topiclab-backend`. This is a non-fatal fallback (no-op in local dev when
`ACCOUNT_SYNC_ENABLED=false`).

---

## 8. LLM Routing Fix

**File:** `app/services/profile_helper/prompts.py`

Added an explicit rule to `META_SYSTEM_PROMPT`: the LLM **must** call
`read_skill` before performing any task (asking questions or writing the
profile). This prevents the LLM from acting on its training knowledge alone
after seeing a blank profile template via `read_profile`, which caused it
to ask the user for every field individually instead of extracting from the
pasted AI memory content.

---

## Backwards Compatibility

- All existing API endpoints are preserved.
- `reset()` (the full reset, used by tests) remains available but is no longer
  wired to the HTTP endpoint; the endpoint now calls `reset_conversation_only`.
- The `import-ai-memory` (standard) skill is still present; the v2 skill is
  toggled via a filter in `_build_backend_tools()` (currently `import-ai-memory`
  is hidden; swap the filter to switch between them).
- `export_to_pdf` / `export_to_image` require a Chromium-based browser at one
  of the standard macOS/Linux paths; if not found, the endpoint returns HTTP 503.
