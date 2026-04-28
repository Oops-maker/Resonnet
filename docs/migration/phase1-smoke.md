# Phase 1 Smoke Scenarios

**How to run**: Each smoke is a curl command or Python assertion against the running local stack.  
**Stack required**: Resonnet :8000 + topiclab-backend :8001 + frontend :3000  
**Baseline**: Run before any code change. Mark each as PASS/FAIL/SKIP.

---

## Group A: Existing behavior that must not break

### A-01: Session creation (anonymous)
```bash
curl -s http://127.0.0.1:8000/profile-helper/session
```
**Expect**: 200, `{"session_id": "<uuid>"}`  
**Baseline**: PASS / FAIL

---

### A-02: Chat — welcome blocks returned on first message
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s -N -X POST http://127.0.0.1:8000/profile-helper/chat/blocks \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SID\", \"message\": \"建立我的分身\"}" | head -5
```
**Expect**: SSE stream, first event contains `"type":"text"` with privacy notice  
**Baseline**: PASS / FAIL

---

### A-03: Profile parser returns structure (not crash)
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s http://127.0.0.1:8000/profile-helper/profile/$SID/structured | python3 -c "import sys,json; d=json.load(sys.stdin); print('completion:', d['completion'])"
```
**Expect**: `completion: {...}` dict, no error  
**Baseline**: PASS / FAIL

---

### A-04: Scale submit and retrieve
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s -X POST http://127.0.0.1:8000/profile-helper/scales/submit \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SID\", \"scale_name\": \"rcss\", \"answers\": {}, \"scores\": {\"csi\": 5.0}}" | python3 -c "import sys,json; print(json.load(sys.stdin))"
curl -s http://127.0.0.1:8000/profile-helper/scales/$SID | python3 -c "import sys,json; d=json.load(sys.stdin); print('has rcss:', 'rcss' in d.get('scales', {}))"
```
**Expect**: submit → `{"ok": true}`, retrieve → `has rcss: True`  
**Baseline**: PASS / FAIL

---

### A-05: Session reset returns 200
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s -X POST http://127.0.0.1:8000/profile-helper/session/reset/$SID | python3 -c "import sys,json; print(json.load(sys.stdin))"
```
**Expect**: `{"ok": true, "session_id": "..."}`  
**Baseline**: PASS / FAIL

---

### A-06: Scientists/famous returns top3 (anonymous, no LLM wait)
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
time curl -s http://127.0.0.1:8000/profile-helper/profile/$SID/scientists/famous | python3 -c "import sys,json; d=json.load(sys.stdin); print('top3:', len(d.get('top3',[])))"
```
**Expect**: `top3: 3`, response time < 1 second (empty profile → no LLM)  
**Baseline**: PASS with time=8s (FAIL on time) / PASS / FAIL

---

### A-07: Download profile returns markdown text
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s http://127.0.0.1:8000/profile-helper/download/$SID | head -3
```
**Expect**: Markdown text starting with `# 科研人员画像`  
**Baseline**: PASS / FAIL

---

## Group B: New behavior after Phase 1

### B-01: Empty profile — scientists/famous returns in < 1 second (no LLM call)
```bash
SID=$(curl -s http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
START=$(date +%s%3N)
curl -s http://127.0.0.1:8000/profile-helper/profile/$SID/scientists/famous > /dev/null
END=$(date +%s%3N)
echo "elapsed: $((END-START))ms"
```
**Expect (after Phase 1)**: elapsed < 500ms  
**Baseline**: ~8000ms (FAIL — this is what we're fixing)

---

### B-02: Profile with CSI data — first request computes, second request hits cache
```python
import httpx, json, time

# Setup: build a session with a profile that has CSI data
# (Use the existing profile from our test session)
SID = "7eec57ed-33a5-4d5e-997a-01a9fc3444a9"

# First request
t1 = time.time()
r1 = httpx.get(f"http://127.0.0.1:8000/profile-helper/profile/{SID}/scientists/famous")
t2 = time.time()
first_time = t2 - t1

# Second request (should be cached)
t3 = time.time()
r2 = httpx.get(f"http://127.0.0.1:8000/profile-helper/profile/{SID}/scientists/famous")
t4 = time.time()
second_time = t4 - t3

print(f"First: {first_time:.2f}s, Second: {second_time:.2f}s")
assert second_time < 0.5, "Cache miss on second request"
assert r1.json()["top3"][0]["name"] == r2.json()["top3"][0]["name"], "Different results"
```
**Expect (after Phase 1)**: first ≤ 10s (LLM), second < 0.5s (cache hit), same results  
**Baseline**: Both ~8s (FAIL — no cache)

---

### B-03: Cache invalidated when profile content changes
```python
# After profile is updated (content changes), cache should recompute
# Method: manually change profile.md content, then request /scientists/famous
# Verify: personalized reason changes (different profile → different match)
```
**Expect (after Phase 1)**: cache miss after profile content change  
**Baseline**: N/A (no cache exists yet)

---

### B-04: Session reset clears conversation, profile still in digital_twins
```bash
# 1. Register + build a profile (or use existing session with profile)
# 2. Reset session
SID="7eec57ed-33a5-4d5e-997a-01a9fc3444a9"
curl -s -X POST http://127.0.0.1:8000/profile-helper/session/reset/$SID

# 3. Check: profile page still shows the profile
curl -s http://127.0.0.1:8000/profile-helper/profile/$SID/structured | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print('name:', d.get('name'))"
```
**Expect (after Phase 1)**: name still shows (profile not wiped), chat history empty  
**Baseline**: Currently reloads profile from disk (works for logged-in), but chat history also reloaded (PARTIAL PASS)

---

### B-05: Logged-in user profile survives Resonnet restart
```bash
# 1. Register a user, build a profile
# 2. Kill and restart Resonnet
# 3. GET /session?session_id={same_id} with auth token
# 4. Check profile is restored
# (Requires AUTH_MODE=jwt + real user, or mock)
```
**Expect (after Phase 1)**: profile restored from digital_twins if workspace file missing  
**Baseline**: Restored from workspace file if exists; FAIL if file missing after restart with new workspace

---

## Smoke Run Script

```bash
#!/bin/bash
# run_smokes.sh — run all Phase 1 smokes
set -e
echo "=== Phase 1 Smoke Run ==="

# Start services check
curl -sf http://127.0.0.1:8000/health > /dev/null && echo "✅ Resonnet :8000" || { echo "❌ Resonnet not running"; exit 1; }
curl -sf http://127.0.0.1:8001/health > /dev/null && echo "✅ topiclab-backend :8001" || echo "⚠️  topiclab-backend not running (some smokes will skip)"

# A-01
SID=$(curl -sf http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
[ -n "$SID" ] && echo "✅ A-01 session creation" || echo "❌ A-01"

# A-03
curl -sf http://127.0.0.1:8000/profile-helper/profile/$SID/structured | python3 -c "import sys,json; json.load(sys.stdin)['completion']" && echo "✅ A-03 structured profile" || echo "❌ A-03"

# A-04
curl -sf -X POST http://127.0.0.1:8000/profile-helper/scales/submit \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SID\", \"scale_name\": \"rcss\", \"answers\": {}, \"scores\": {\"csi\": 5.0}}" | python3 -c "import sys,json; assert json.load(sys.stdin)['ok']" && echo "✅ A-04 scale submit" || echo "❌ A-04"

# A-05
curl -sf -X POST http://127.0.0.1:8000/profile-helper/session/reset/$SID | python3 -c "import sys,json; assert json.load(sys.stdin)['ok']" && echo "✅ A-05 session reset" || echo "❌ A-05"

# A-06 + B-01 (timing)
START=$(date +%s%3N)
SID2=$(curl -sf http://127.0.0.1:8000/profile-helper/session | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
COUNT=$(curl -sf http://127.0.0.1:8000/profile-helper/profile/$SID2/scientists/famous | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('top3',[])))")
END=$(date +%s%3N)
ELAPSED=$((END-START))
[ "$COUNT" = "3" ] && echo "✅ A-06 famous top3=3" || echo "❌ A-06 top3=$COUNT"
[ $ELAPSED -lt 1000 ] && echo "✅ B-01 empty profile <1s (${ELAPSED}ms)" || echo "❌ B-01 empty profile too slow (${ELAPSED}ms)"

# A-07
curl -sf http://127.0.0.1:8000/profile-helper/download/$SID2 | grep -q "科研人员画像" && echo "✅ A-07 download markdown" || echo "❌ A-07"

echo "=== Done ==="
```

Save as `docs/migration/run_smokes.sh`, run with `bash run_smokes.sh`.
