"""AI 비서에 연결(app/api/mcp_link.py, 원격 MCP 시험판): 열쇠가 그 사람 · 그 판에서만 통하는지, MCP 요청에 맞게 답하는지."""

from tests.test_api_flow import H1, H2, client, env  # noqa: F401  (픽스처)


def rpc(c, key, method, params=None, i=1):
    return c.post(f"/mcp/{key}", json={"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}})


def test_link_works_only_with_the_latest_key(client):  # noqa: F811
    assert client.get("/mcp/link", headers=H1).json() == {"connected": False, "expires_at": None}
    old = client.post("/mcp/link", headers=H1).json()["key"]
    assert client.get("/mcp/link", headers=H1).json()["connected"]
    init = rpc(client, old, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
    assert init["protocolVersion"] == "2025-06-18" and init["capabilities"] == {"tools": {}}
    assert client.post(f"/mcp/{old}", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    assert [t["name"] for t in rpc(client, old, "tools/list").json()["result"]["tools"]] == ["import_diaries", "write_diary", "recent_diaries"]

    new = client.post("/mcp/link", headers=H1).json()["key"]   # 새 주소 → 예전 주소는 바로 끊김
    assert rpc(client, old, "ping").status_code == 401
    assert rpc(client, new, "ping").json()["result"] == {}
    uid, kid, exp, sig = new.split(".")
    other = client.post("/mcp/link", headers=H2).json()["key"].split(".")[0]
    for bad in (f"{uid}.{kid}.{exp}.{'0' * 32}", f"{other}.{kid}.{exp}.{sig}", f"{uid}.{kid}.{int(exp) + 1}.{sig}", "x", "a.b.c.d"):
        assert rpc(client, bad, "ping").status_code == 401, bad
    assert client.delete("/mcp/link", headers=H1).status_code == 204
    assert rpc(client, new, "ping").status_code == 401


def test_tools_answer_in_mcp_shape(client):  # noqa: F811
    key = client.post("/mcp/link", headers=H1).json()["key"]
    r = rpc(client, key, "tools/call", {"name": "recent_diaries", "arguments": {"n": 5}}).json()["result"]
    assert not r["isError"] and r["structuredContent"] == {"diaries": [], "waiting": 0}
    bad = rpc(client, key, "tools/call", {"name": "import_diaries", "arguments": {"entries": [{"text": "글", "date": "2026/11/01"}]}}).json()
    assert bad["result"]["isError"] and "YYYY-MM-DD" in bad["result"]["content"][0]["text"]
    assert rpc(client, key, "tools/call", {"name": "nope"}).json()["error"]["code"] == -32601
    assert rpc(client, key, "resources/list").json()["error"]["code"] == -32601
