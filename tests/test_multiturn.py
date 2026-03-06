"""快速多轮对话端到端验证脚本（从容器内直连 FastAPI）。"""
import http.client
import json
import sys


def post_json(path: str, data: dict) -> tuple[dict, int]:
    conn = http.client.HTTPConnection("localhost", 8000)
    body = json.dumps(data).encode()
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    return json.loads(r.read()), r.status


def stream_chat(path: str, data: dict) -> str:
    conn = http.client.HTTPConnection("localhost", 8000, timeout=180)
    body = json.dumps(data).encode()
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    texts: list[str] = []
    errors: list[str] = []
    for raw in r:
        line = raw.decode().strip()
        if not line.startswith("data:") or line == "data: [DONE]":
            continue
        try:
            obj = json.loads(line[5:])
        except Exception:
            continue
        if obj.get("type") == "assistant_delta":
            texts.append(obj.get("content") or "")
        if obj.get("error"):
            errors.append(str(obj["error"]))
    if errors:
        print("  [ERRORS]:", "; ".join(errors))
    return "".join(texts)


def main():
    slug = "tashan-profile-helper-demo"
    base = f"/agent-links/{slug}"

    print("=== 多轮对话 API 测试 ===")
    resp, status = post_json(f"{base}/session", {})
    assert status == 200, f"session创建失败: {status}"
    sid = resp["session_id"]
    print(f"Session: {sid}")

    print("\nTurn 1: 我叫房泽锐，记住我的名字")
    t1 = stream_chat(f"{base}/chat", {"session_id": sid, "message": "我叫房泽锐，记住我的名字"})
    print(f"  回复: {t1[:120]}")

    print("\nTurn 2: 我叫什么名字？")
    t2 = stream_chat(f"{base}/chat", {"session_id": sid, "message": "我叫什么名字？"})
    print(f"  回复: {t2[:120]}")

    ok = "房泽锐" in t2
    print(f"\n记忆测试: {'通过 ✓' if ok else '失败 ✗'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
