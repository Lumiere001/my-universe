"""WS15 관측 보고서(관측 상태 · 한계) · JSON 내려받기. 다른 사람 이름은 가리지 않는다(2026-10-13 동규 결정 12)."""
import json

from app.repository import views
from tests.test_api_flow import H1, H2, client, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, DAY2, NAMES, env  # noqa: F401  (env 픽스처)

RECORD_KEYS = {"id", "status", "written_at", "title", "weather", "crisis", "info", "thoughts", "relations", "past",
               "reached", "message", "next_question", "observation", "text",
               "source", "day", "day_basis", "day_check", "confirmed", "record_type"}
THOUGHT_KEYS = {"id", "text", "kind", "grateful", "certainty", "value", "quote", "self_change", "topic", "star_id",
                "sun_id", "domain", "people", "other", "original", "state"}


def two_days(client):  # noqa: F811
    _, ev1 = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev2 = write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    return ev1[-1][1], ev2[-1][1]


##################################################
# 관측 상태 · 한계
##################################################

def _r(**kw):
    return {"id": "e2", "day_basis": "확실", "day_check": False, **kw}


T = [{"id": "e2-t00", "star_id": "s1"}]


def test_observation_states():
    rel = lambda typ, line="실선", frm="e1": {"to": "e2-t00", "from_record": frm, "type": typ, "line": line}  # noqa: E731
    past = {"e1-t00": {"star_id": "s1"}}
    assert views.observation(_r(), [], [], [], {})["state"] == "생각이 없는 글"
    assert views.observation(_r(), T, [], [], {})["state"] == "비교할 지난 글 없음"
    # 겹치면 해소 > 바뀜 > 긴장 > 어긋남 > 이어짐(PRD §5.4), 목록 밖(목표 충돌)은 그 뒤
    assert views.observation(_r(), T, [rel("이어짐"), rel("해소"), rel("바뀜")], ["e1-t00"], past)["state"] == "해소"
    assert views.observation(_r(), T, [rel("목표 충돌"), rel("어긋남")], ["e1-t00"], past)["state"] == "어긋남"
    assert views.observation(_r(), T, [rel("목표 충돌")], ["e1-t00"], past)["state"] == "목표 충돌"
    # 같은 글 안의 관계는 지난 글과의 관측이 아니다
    assert views.observation(_r(), T, [rel("긴장", frm="e2")], ["e1-t00"], past)["state"] == "이어진 지난 생각 없음"
    assert views.observation(_r(), T, [], ["e1-t00"], {"e1-t00": {"star_id": "s9"}})["state"] == "처음 쓰는 주제"


def test_observation_limits():
    o = views.observation(_r(day_basis="추정"), T, [{"to": "e2-t00", "from_record": "e1", "type": "이어짐", "line": "점선"}],
                          ["e1-t00", "e1-t01"], {})
    text = " ".join(o["limits"])
    assert "AI" in text and "지난 생각 2개와만" in text and "점선" in text and "쓴 날로 추정" in text
    o = views.observation(_r(day_basis="추정", day_check=True), T, [], [], {})
    assert any("날짜를 하나로 읽지 못" in x for x in o["limits"]) and not any("쓴 날로 추정" in x for x in o["limits"])
    assert views.observation(_r(), T, [], [], {})["limits"] == [o["limits"][0]]   # 확실한 날 · 비교 없음: AI 추정 한 줄만
    assert views.observation(_r(), [], [], [], {})["limits"] == []


def test_result_card_carries_observation(client):  # noqa: F811
    r1, r2 = two_days(client)
    assert r1["observation"]["state"] == "비교할 지난 글 없음"
    assert any("쓴 날로 추정" in x for x in r1["observation"]["limits"])          # 글 속 날짜 없음 → 추정
    types = {x["type"] for x in r2["relations"] if x["from_entry"] == r1["id"]}
    assert r2["observation"]["state"] in types
    assert any(f"지난 생각 {len(r2['past'])}개와만" in x for x in r2["observation"]["limits"])
    assert client.get(f"/diary/{r2['id']}", headers=H1).json()["observation"] == r2["observation"]


##################################################
# JSON 내려받기
##################################################

def test_export_one_record_schema(client):  # noqa: F811
    r1, _ = two_days(client)
    out = client.get(f"/export/{r1['id']}", headers=H1).json()
    assert set(out) == {"schema", "exported_at", "scope", "records", "domains"}
    assert out["schema"] == "my-universe-export/1" and out["scope"] == "entry" and len(out["records"]) == 1
    rec = out["records"][0]
    assert set(rec) == RECORD_KEYS
    assert rec["text"] == DAY1[1] and rec["title"] == DAY1[0] and rec["id"] == r1["id"]
    assert rec["source"] == "텍스트" and rec["day"] == "2026-10-01" and rec["day_basis"] == "추정"   # WS11 기록 칸
    assert rec["observation"] == r1["observation"] and rec["message"]["text"]                        # 보고서
    assert rec["thoughts"] and all(set(t) == THOUGHT_KEYS for t in rec["thoughts"])
    # 영역: 생각이 가리키는 해 · 작은 별이 모두 domains 에 있고, 생각에 영역 이름이 붙는다
    suns = {d["id"]: d for d in out["domains"]}
    for t in rec["thoughts"]:
        assert t["domain"] == suns[t["sun_id"]]["name"]
        assert t["star_id"] in {x["id"] for x in suns[t["sun_id"]]["topics"]}


def test_export_keeps_real_names(client):  # noqa: F811
    """결정 12: 가리지 않는다. 사람은 id 대신 실명으로, 사람 목록(가명 표)은 넣지 않는다."""
    _, r2 = two_days(client)
    out = client.get(f"/export/{r2['id']}", headers=H1).json()
    blob = json.dumps(out, ensure_ascii=False)
    assert all(n in blob for n in NAMES)                                         # 원문 · 인용의 실명 그대로
    people = {n for t in out["records"][0]["thoughts"] for n in t["people"]}
    assert "민준" in people and not any(n.startswith("p_") for n in people)
    pid = {p["name"]: p["id"] for p in client.get("/people", headers=H1).json()["people"]}
    assert not any(i in blob for i in pid.values())                              # 사람 id 0건
    assert "people" not in out and "people_questions" not in out["records"][0]
    assert client.get(f"/export/{r2['id']}?mask=1", headers=H1).json()["records"][0]["text"] == DAY2[1]   # 가리기 선택지 없음


def test_export_all_in_written_order(client):  # noqa: F811
    r1, r2 = two_days(client)
    client.post("/people", headers=H1, json={"name": "하린", "relation": "동생"})
    out = client.get("/export", headers=H1).json()
    assert out["scope"] == "all" and [r["id"] for r in out["records"]] == [r1["id"], r2["id"]]   # 먼저 쓴 것부터
    assert [r["text"] for r in out["records"]] == [DAY1[1], DAY2[1]]
    rels = out["records"][1]["relations"]
    assert rels and {x["id"] for x in rels} == {x["id"] for x in r2["relations"]}                # 관계
    assert "하린" not in json.dumps(out, ensure_ascii=False)                                     # 글에 안 나온 사람 목록은 없음


def test_export_isolation_and_errors(client):  # noqa: F811
    r1, _ = two_days(client)
    assert client.get("/export").status_code == 401
    assert client.get(f"/export/{r1['id']}", headers=H2).status_code == 404       # 남의 기록
    assert client.get("/export/e_nothing", headers=H1).status_code == 404
    assert client.get("/export/bad%20id", headers=H1).status_code == 422
    other = client.get("/export", headers=H2).json()
    assert other["records"] == [] and other["domains"] == []
    client.delete(f"/diary/{r1['id']}", headers=H1)
    assert r1["id"] not in [r["id"] for r in client.get("/export", headers=H1).json()["records"]]
    assert client.get(f"/export/{r1['id']}", headers=H1).status_code == 404       # 지운 기록은 내려받기에도 없음
