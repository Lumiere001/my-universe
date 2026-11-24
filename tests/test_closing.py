"""시험 기간 끝(2026-11-25 동규): 닫히면 새 기록 · 대화 · 고치기는 403 service_closed, 읽기 · 내려받기 · 지우기 · 마치며 의견은 그대로.
마치며 의견은 '운영자가 읽어요' 안내를 보고 보낸 글이라 운영 화면에서 읽힌다(가명). 알림 예약은 보내지 않는다."""
from app.core import config
from tests.test_api_flow import H1, write
from tests.test_graph_flow import DAY1, env  # noqa: F401  (env 픽스처)
from tests.test_ws22_ops import H2, HA, c  # noqa: F401  (c 픽스처: U1 · U2 · 운영자)


def test_closed_blocks_writes_keeps_reads_export_delete_and_closing_note(c, monkeypatch):  # noqa: F811
    _, ev = write(c, *DAY1, "2026-10-01T22:00:00+09:00")   # 닫기 전에 쓴 한 편
    eid = ev[-1][1]["id"]
    monkeypatch.setattr(config, "SERVICE_CLOSED", True)
    assert c.get("/health").json()["closed"] is True
    for method, path, body in (("post", "/diary/stream", {"text": "새 글", "written_at": "2026-11-25T22:00:00+09:00"}),
                               ("post", "/talk", {}), ("patch", "/settings", {"tone": "담백하게"}), ("post", "/mcp/link", {})):
        r = getattr(c, method)(path, headers=H1, json=body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "service_closed", path
    assert [r["id"] for r in c.get("/export", headers=H1).json()["records"]] == [eid]   # 내 일기 받기
    assert c.post("/feedback", headers=H2, json={"target": "app", "value": "마치며 의견", "text": "  "}).status_code == 422
    assert c.post("/feedback", headers=H2, json={"target": "app", "value": "마치며 의견", "ops": True,
                                                 "text": "지난 생각을 기억해 줘서 좋았어요"}).status_code == 200
    body = c.get("/ops/feedback", headers=HA).json()
    sent = [x for x in body["items"] if x["value"] == "마치며 의견"]
    assert len(sent) == 1 and "좋았어요" in sent[0]["text"] and sent[0]["via"]   # 이름 가명은 test_ws22_ops 가 봄
    assert "마치며 의견" not in body["not_consented"]
    assert c.get("/ops/summary", headers=HA).json()["feedback_text"]["closing"] == 1
    assert c.delete(f"/diary/{eid}", headers=H1).status_code in (200, 204)   # 지우기는 닫혀도 됨
    monkeypatch.setattr(config, "CRON_SECRET", "s")
    assert c.post("/push/due", headers={"X-Cron-Secret": "s"}).json() == {"off": True, "sent": 0}
