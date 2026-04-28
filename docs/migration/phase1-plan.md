# Phase 1 Migration Plan

**Goal**: Fix the three most visible user-facing issues without any schema changes.  
**Scope**: Resonnet only — `sessions.py`, `scientist_match.py`, `profile_helper.py`  
**No changes to**: topiclab-backend, database schema, frontend, API contracts

---

## Changes

### Change 1: `save_profile()` — sync to `digital_twins` for logged-in users

**File**: `app/services/profile_helper/sessions.py`  
**What**: After writing `profile.md` to filesystem, also call topiclab-backend to upsert `digital_twins.role_content`  
**Why**: Profile is currently only in Resonnet filesystem; if server restarts before session recovery, profile is gone for users who haven't published  
**How**: Resonnet already calls `sync_twin_record` (via `integrations/account_sync.py`) in `_sync_twin_agent()`. We need to also write `role_content` there.

```python
# Current: _sync_twin_agent() only syncs agent metadata, not profile content
# Proposed: also write role_content = current profile markdown
```

**Risk**: Low. `_sync_twin_agent()` already exists and is called in `save_profile()`. Adding `role_content` to the payload is additive.

---

### Change 2: Session reconstruction — pull from `digital_twins` if filesystem missing

**File**: `app/services/profile_helper/sessions.py` → `_new_session()`  
**What**: When reconstructing a session for a logged-in user and workspace file is missing, call topiclab-backend to get `digital_twins.role_content`  
**Why**: Server restart clears in-memory sessions. File may also be missing (new server, disk replaced). Currently user sees blank template.  
**How**: Add fallback in `_new_session()`:

```python
if user_id:
    pdir = _profiles_dir(user_id)
    pf = pdir / "profile.md"
    if pf.exists():
        profile = pf.read_text()     # existing path
    else:
        # NEW: try to pull from digital_twins
        profile = _pull_profile_from_account(user_id) or _load_template_with_date()
```

**Risk**: Low. Additive fallback. Only triggered if local file missing.

---

### Change 3: Scientist match cache

**File**: `app/services/profile_helper/scientist_match.py`  
**What**: Cache `match_famous_scientists()` result (including personalized reasons) keyed by SHA256 of profile content  
**Why**: Currently takes ~8 seconds on every profile page load (LLM call)  
**How**:

```python
def get_or_compute_match(session: dict, parsed: dict) -> dict:
    user_id = session.get("user_id")
    profile_content = session.get("profile", "")
    profile_hash = sha256(profile_content)

    if user_id:
        cache_path = _profiles_dir(user_id) / "scientist_cache.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if cached.get("h") == profile_hash:
                return cached["result"]   # cache hit

    result = match_famous_scientists(parsed)  # math only, fast

    # Only call LLM if profile has actual data
    if parsed.get("cognitive_style", {}).get("csi") is not None:
        result["top3"] = _generate_personalized_reasons(result["top3"], parsed)

    if user_id:
        cache_path.write_text(json.dumps({"h": profile_hash, "result": result}))

    return result
```

**Risk**: Low. Cache miss falls back to current behavior. Cache is per-user filesystem file.

---

### Change 4: Skip LLM for empty profiles

**File**: `app/services/profile_helper/scientist_match.py`  
**What**: Do not call `_generate_personalized_reasons()` if profile has no CSI/RAI data  
**Why**: Currently triggers an 8-second LLM call even when profile is blank  
**Guard**:

```python
has_data = parsed.get("cognitive_style", {}).get("csi") is not None
if has_data:
    top3 = _generate_personalized_reasons(top3, parsed)
```

**Risk**: None. Template reasons are still returned for empty profiles.

---

### Change 5: `session/reset` — clear conversation, keep profile in `digital_twins`

**File**: `app/api/profile_helper.py` → `session_reset()`  
**What**: Reset only clears `messages.json` and loads blank template; does NOT touch `digital_twins`  
**Why**: Currently `sessions.reset()` calls `_new_session()` which reloads from disk — for logged-in users this already works, but it reloads the existing profile which is confusing when user wants to rebuild from scratch  

Correct behavior:
- `digital_twins.role_content` stays unchanged (last completed build)
- `workspace/profile.md` stays unchanged (last save)
- Only `messages.json` is cleared
- `session.profile` is reset to blank template
- Profile page: still shows last completed profile from `digital_twins`
- Chat page: shows empty conversation, ready for new build

```python
@router.post("/session/reset/{session_id}")
async def session_reset(session_id, auth_ctx):
    uid = _get_uid(auth_ctx)
    _ = _get_session_for_user(session_id, uid)
    profile_sessions.reset_conversation_only(session_id)  # NEW function
    return {"ok": True, "session_id": session_id}
```

**Risk**: Low. Behavioral change for reset: previously showed existing profile in chat, now shows blank template. Profile page unchanged.

---

## Files Changed

| File | Change |
|------|--------|
| `app/services/profile_helper/sessions.py` | Changes 1, 2, 5 |
| `app/services/profile_helper/scientist_match.py` | Changes 3, 4 |
| `app/api/profile_helper.py` | Change 5 (endpoint) |
| `app/integrations/account_sync.py` | Change 1 (add role_content to sync payload) |

## Files NOT Changed

- `block_agent.py` — no change
- `profile_parser.py` — no change
- `prompts.py` — no change
- `tools.py` — no change
- `libs/` — no change
- topiclab-backend — no change
- frontend — no change

---

## Smoke Scenarios (defined in phase1-smoke.md)
