# Profile Helper: Final Architecture

**Version**: v1.0  
**Date**: 2026-04-08  
**Status**: Approved — implementation guide

---

## Architectural Decisions (all confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Profile canonical store | `digital_twins` table (topiclab-backend) + Resonnet filesystem as working cache | Profile belongs to the user account, not a server or session |
| Session concept | Work window — conversation history for the current build | Reset = new build from scratch, old profiles preserved |
| CLI access | HTTP API (same endpoints as web) | Simplest; Transport Adapter pattern renders blocks as text |
| Anonymous users | Supported, 24h TTL; migrate to account on login | Low friction for first-time users |
| Historical versions | `profile_builds` table (new) | Separate, clean history independent of agent_name semantics |
| Scale data (AMS/RCSS/Mini-IPIP) | topiclab-backend | User measurement data belongs with the user account |

---

## System Boundaries

```
topiclab-backend                         Resonnet
(User data authority)                    (AI compute + working storage)

┌────────────────────────┐              ┌─────────────────────────────┐
│ users                  │              │ workspace/                   │
│ digital_twins          │◄────sync─────│   users/{uid}/profile/       │
│ profile_builds         │              │     profile.md (cache)       │
│ scales (NEW)           │              │     messages.json            │
│ verification_codes     │              │     scientist_cache.json     │
│ openclaw_*             │              │                              │
│                        │              │   anon/{token}/              │
│                        │◄────auth─────│     profile.md (24h TTL)     │
│                        │              │     messages.json            │
└────────────────────────┘              └─────────────────────────────┘
         ▲                                           ▲
         │ JWT                                       │ SSE / HTTP
         │                                           │
    Frontend / CLI  ─────────────────────────────────┘
```

---

## Data Model

### topiclab-backend (new and changed tables)

#### `digital_twins` (existing — minimal change)

The existing table stores the **currently active profile** for a user. One row per user per `agent_name`.

```sql
digital_twins (
  id            SERIAL PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  agent_name    VARCHAR(100) NOT NULL DEFAULT 'my_twin',
  display_name  VARCHAR(100),
  role_content  TEXT,          -- current active profile markdown
  session_id    VARCHAR(100),  -- session that last wrote this
  source        VARCHAR(50) DEFAULT 'profile_twin',
  visibility    VARCHAR(20) DEFAULT 'private',
  exposure      VARCHAR(20) DEFAULT 'brief',
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, agent_name)
)
```

#### `profile_builds` (NEW — version history)

Every completed profile build creates one row here. Immutable after creation.

```sql
profile_builds (
  id            SERIAL PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id    VARCHAR(100),   -- which build session produced this
  content       TEXT NOT NULL,  -- full profile.md content at completion
  display_name  VARCHAR(100),   -- user-given name for this build
  build_method  VARCHAR(50),    -- 'ai_memory' | 'direct' | 'manual'
  is_active     BOOLEAN NOT NULL DEFAULT FALSE,  -- at most one TRUE per user
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
)

CREATE INDEX idx_profile_builds_user_id ON profile_builds(user_id);
CREATE INDEX idx_profile_builds_active ON profile_builds(user_id, is_active)
  WHERE is_active = TRUE;
```

Invariant: at most one `is_active=TRUE` per `user_id` (enforced in application layer).

#### `scales` (NEW — replace Resonnet scales.json)

```sql
scales (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scale_name  VARCHAR(50) NOT NULL,  -- 'rcss' | 'ams' | 'mini_ipip'
  answers     JSONB,                 -- raw question answers
  scores      JSONB,                 -- computed dimension scores
  result_summary JSONB,
  source      VARCHAR(20) DEFAULT 'self_report',  -- 'self_report' | 'ai_inferred'
  taken_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, scale_name, taken_at)  -- allows retakes
)

CREATE INDEX idx_scales_user_scale ON scales(user_id, scale_name);
```

Most recent row per `scale_name` is considered current. Old rows are history.

### Resonnet workspace (working storage)

```
workspace/
├── users/
│   └── {user_id}/
│       └── profile/
│           ├── profile.md              ← working copy of active build
│           ├── messages.json           ← current build session conversation
│           └── scientist_cache.json    ← cached match result
│               (invalidated when profile content changes)
│
└── anon/
    └── {anon_token}/                   ← TTL: 24 hours
        ├── profile.md
        └── messages.json
```

No more `profiles/{name}-{session_id[:8]}.md` pattern. Path is always stable per identity.

---

## Session Lifecycle

### Starting a new build

```
User opens /profile-helper (or: topiclab profile build)

1. Frontend: GET /profile-helper/session?session_id={existing|null}

2. Backend (get_or_create):
   IF user_id AND workspace/users/{uid}/profile/profile.md exists:
     → load into session (resume editing previous work-in-progress)
   ELSE IF user_id AND digital_twins.role_content exists:
     → pull from digital_twins into workspace cache
     → load into session
   ELSE:
     → load blank template
   → also load messages.json as conversation history

3. User converses with AI to build profile
   → save_profile() called incrementally during build
   → writes workspace/users/{uid}/profile/profile.md

4. Build complete (AI calls show_actions with "done")
   → POST /profile-helper/publish-to-library OR auto-save
   → INSERT INTO profile_builds (content, is_active=TRUE)
   → UPDATE digital_twins SET role_content=?, is_active=TRUE
   → other profile_builds rows: SET is_active=FALSE
```

### Resetting to build again

```
User clicks "Reset Session" (or: topiclab profile reset)

POST /profile-helper/session/reset/{session_id}

1. Clear workspace/users/{uid}/profile/messages.json  ← conversation gone
2. Load blank template into session.profile           ← start fresh
3. Keep workspace/users/{uid}/profile/profile.md unchanged  ← still accessible
4. Keep all profile_builds rows intact                ← history preserved
5. digital_twins.role_content still points to last completed build

Result: Chat window is empty. User starts new conversation.
        "My Profiles" still shows all previous completed builds.
```

### Viewing profile history

```
GET /auth/profile-builds          (topiclab-backend)
→ returns all profile_builds for current user, newest first
→ frontend renders as cards in "My Profiles" section

GET /auth/profile-builds/{id}     
→ returns full content of specific build
→ user can view, activate, or use as starting point

POST /auth/profile-builds/{id}/activate
→ SET is_active=TRUE for this build, FALSE for all others
→ UPDATE digital_twins.role_content = this build's content
→ copy content to workspace/users/{uid}/profile/profile.md
→ profile page now shows this activated build
```

### Anonymous user flow

```
Anonymous user opens /profile-helper

1. Frontend: generates anon_token (UUID), stores in localStorage
2. GET /profile-helper/session?anon_token={token}
3. Backend: creates workspace/anon/{token}/ with blank template
4. User builds profile — stored in workspace/anon/{token}/

   At any point: "Login to save your profile"

5. User registers/logs in → POST /auth/login
6. Backend migration:
   - workspace/anon/{token}/profile.md → workspace/users/{uid}/profile/profile.md
   - INSERT INTO profile_builds (content, user_id=new_user_id)
   - UPDATE digital_twins
   - delete workspace/anon/{token}/

7. anon_token in localStorage replaced by session_id pointing to user session

If user never logs in: workspace/anon/{token}/ deleted after 24 hours.
```

---

## API Changes

### topiclab-backend (new endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/profile-builds` | List all profile builds for current user |
| GET | `/auth/profile-builds/{id}` | Get specific build content |
| POST | `/auth/profile-builds/{id}/activate` | Activate a historical build |
| POST | `/auth/scales` | Submit scale results (replaces Resonnet scales) |
| GET | `/auth/scales` | Get all scale results for current user |
| GET | `/auth/scales/{scale_name}` | Get most recent result for specific scale |

### Resonnet (changed behavior)

| Endpoint | Change |
|----------|--------|
| `POST /session/reset/{id}` | Clear messages only; reload blank template; do NOT touch profile_builds or digital_twins |
| `POST /publish-to-library` | Also INSERT INTO profile_builds; set is_active=TRUE |
| `save_profile()` internal | Also sync to digital_twins.role_content for logged-in users |
| `GET /profile/{id}/scientists/famous` | Use hash-based cache from scientist_cache.json |
| `POST /scales/submit` | Forward to topiclab-backend `/auth/scales` (deprecate local scales.json) |
| `GET /scales/{id}` | Read from topiclab-backend `/auth/scales` |

---

## Migration Plan

### Phase 1 — Fix the most visible user issues (this sprint)

**Goal**: Profile is never lost on server restart or navigation.

1. `save_profile()` syncs to `digital_twins.role_content` for logged-in users
2. Session reconstruction on restart: if workspace file missing, pull from `digital_twins`
3. Scientist match cache (hash-based, workspace file)
4. Skip LLM in `/scientists/famous` if profile is empty
5. `session/reset` preserves existing profile in `digital_twins`

No new tables needed. No schema change. Changes only in Resonnet `sessions.py` and `scientist_match.py`.

### Phase 2 — Multi-version profile history (next sprint)

1. Add `profile_builds` table to topiclab-backend
2. `publish-to-library` creates a `profile_builds` row
3. Add profile history UI in "My Profiles" section
4. Reset session → new build → new profile_builds row

### Phase 3 — Scale data migration (future)

1. Add `scales` table to topiclab-backend
2. Resonnet `/scales/submit` forwards to topiclab-backend
3. Deprecate Resonnet `scales.json`
4. Migrate existing scales data

### Phase 4 — Anonymous user migration (future)

1. `anon_token` parameter support in session endpoints
2. 24h cleanup job for `workspace/anon/`
3. Login-time migration of anon profile to user account

### Phase 5 — Stable workspace paths (future)

1. Replace `profiles/{name}-{sid[:8]}.md` pattern with `users/{uid}/profile/profile.md`
2. One-time migration of existing profile files
3. Remove session_id from filesystem path

---

## CLI Support

CLI calls the **same HTTP API** as the web frontend. No Resonnet changes needed for CLI support.

```bash
# Authentication (stores token in ~/.topiclab/config)
topiclab login

# Profile operations
topiclab profile build              # opens interactive build session
topiclab profile list               # lists profile_builds history  
topiclab profile show               # prints current active profile
topiclab profile activate {id}      # activates a historical build
topiclab profile reset              # resets current build session

# Scale operations  
topiclab profile scales             # shows all scale results
topiclab profile scales take rcss   # interactive scale test
```

The CLI's Block adapter renders:
- `ask_choice` → numbered menu with keyboard input
- `ask_text` → prompt with readline
- `show_actions` → list of available commands
- `text` → plain terminal output

The underlying API calls are identical to what the web frontend makes.

---

## What Does NOT Change

- `libs/profile_helper/` Skills and docs — untouched
- `profile_parser.py` — untouched (pure function)
- `scientists_db.py` — untouched
- `block_agent.py` LLM loop logic — untouched (only output handling changes)
- `prompts.py` — untouched
- Authentication flow — untouched

---

## Changelog

| Date | Version | Notes |
|------|---------|-------|
| 2026-04-08 | v1.0 | Final architecture document. All decisions confirmed. |
