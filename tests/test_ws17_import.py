"""WS17 인스타 ZIP 가져오기: 파싱(깨진 한글 · 이어 쓴 게시물 묶기 · 제목 속 날짜) · 미리 보기 API · 같은 ZIP 두 번 → 새 기록 0편 ·
N편 고르면 N편만 · 입력 4종 스크립트. 외부 호출은 가짜(FakeUpstage), 저장소는 메모리. 가상 인물 도담의 지어낸 글만."""
import io
import json
import zipfile

import pytest

from app.core import config
from app.service import importer
from scripts import test_inputs as script
from tests.fixtures import instagram_virtual as fx
from tests.test_api_flow import H1, client  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import U1, env  # noqa: F401  (env 픽스처)


def _post(caption, ts):
    return {"title": caption.encode("utf-8").decode("latin-1"), "creation_timestamp": ts}


def test_parse_fixture_zip():
    recs = importer.records(importer.posts_from_zip(fx.zip_bytes()))
    # 게시물 8개 → 사진만 1개 빠지고, 이어 쓴 2개가 하나로 → 6편, 최근 것부터
    assert len(recs) == 6 and [r["written_at"] for r in recs] == sorted((r["written_at"] for r in recs), reverse=True)
    series = recs[0]
    assert series["parts"] == 2 and series["title"] == "3/28 동아리 해커톤 (1)"
    assert "다섯 시에 고쳤다" in series["text"] and "하늘이가 팀장" in series["text"]          # 깨진 한글 복원 + 두 게시물 합침
    assert "이어짐" not in series["text"] and "=>" not in series["text"] and "(2) 이어서" not in series["text"]
    assert (series["day"], series["day_basis"], series["written_at"]) == ("2026-03-28", "확실", "2026-03-29T01:20:00+09:00")
    assert series["ref"] == f"ig:{fx._ts('2026-03-29T01:20')}"
    one = recs[1]   # 한 줄 글: 제목 없이 본문, 끝 글자 '날'(깨진 바이트 A0)까지 복원
    assert (one["title"], one["text"], one["day_basis"]) == ("", "오늘은 그냥 아무것도 하기 싫은 날", "추정")
    old = recs[2]   # 예전 형식(캡션이 media[0] 안)
    assert old["title"] == "3/22 일요일" and old["day"] == "2026-03-22"
    nodate = recs[3]   # 제목에 날짜 없음 → 게시일(추정)
    assert nodate["title"] == "새벽 생각" and (nodate["day"], nodate["day_basis"]) == ("2026-03-20", "추정")
    newyear = recs[-1]   # 1월 2일에 올린 12/31 일기 → 지난해
    assert (newyear["day"], newyear["day_basis"], newyear["written_at"][:10]) == ("2025-12-31", "확실", "2026-01-02")
    assert not any(r["too_long"] for r in recs) and all(r["text"] for r in recs)


def test_series_markers_only_short_lines_in_merged_posts():
    t = 1774714800
    single = importer.records([_post("3/1 영화\n3편 영화를 몰아서 봤는데 진짜 재밌었다\n좋았다", t)])[0]
    assert "3편 영화를 몰아서" in single["text"]   # 묶이지 않은 글은 줄을 지우지 않음
    merged = importer.records([_post("3/2 일기 (1)\n첫 줄\n(계속)", t), _post("(2) 두 번째 이야기를 길게 이어서 적어 보는 줄입니다", t + 60)])[0]
    assert merged["parts"] == 2 and "(2) 두 번째 이야기를 길게" in merged["text"] and "(계속)" not in merged["text"]
    apart = importer.records([_post("가\n나\n이어짐", t), _post("(2) 다\n라", t + 86400)])   # 하루 넘게 떨어지면 묶지 않음
    assert len(apart) == 2


def test_too_long_and_title_rules():
    t = 1774714800
    long_first = importer.records([_post("아" * 41 + "\n둘째 줄", t)])[0]
    assert long_first["title"] == "" and long_first["text"].startswith("아" * 41)   # 긴 첫 줄은 제목이 아니라 본문
    assert importer.records([_post("제목\n" + "가" * 30, t)], max_text=20)[0]["too_long"] is True
    assert importer.records([_post("", t), {"title": "글"}]) == []   # 캡션 없음 · 시각 없음


def test_zip_without_posts_file():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("messages/inbox.json", "[]")
    with pytest.raises(ValueError, match="posts_1.json"):
        importer.posts_from_zip(buf.getvalue())


def test_sample_zip_matches_fixture():
    """화면의 '예시 ZIP 받기'(public/samples)가 픽스처와 같은 글(다시 만들기: python -m tests.fixtures.instagram_virtual)."""
    assert importer.posts_from_zip(fx.ZIP.read_bytes()) == fx.posts()
    with zipfile.ZipFile(fx.ZIP) as z:
        assert json.loads(z.read(fx.POSTS_JSON)) == fx.posts()


def test_preview_api(client, env, monkeypatch):  # noqa: F811
    posts = script.trim(fx.posts())
    assert client.post("/import/instagram/preview", json={"posts": posts}).status_code == 401
    r = client.post("/import/instagram/preview", headers=H1, json={"posts": posts})
    assert r.status_code == 200
    pv = r.json()
    assert pv["max_posts"] is None and pv["est_seconds_per_post"] > 0 and pv["est_usd_per_post"] > 0   # 상한 없음(기본)
    assert len(pv["posts"]) == 6 and not any(p["imported"] for p in pv["posts"])
    assert pv["posts"][1]["text"].endswith("싫은 날")   # 요청 본문의 앞뒤 공백 떼기가 깨진 바이트(A0)를 지우지 않음
    assert env.fake.calls["record"] == 0   # 미리 보기는 밖으로 보내지 않음
    with env.repo.session(U1) as s:
        assert s.rows("entries") == []     # 저장하지도 않음
    monkeypatch.setattr(config, "IMPORT_MAX_POSTS", 3)
    assert client.post("/import/instagram/preview", headers=H1, json={"posts": posts}).json()["max_posts"] == 3
    bad = [{**posts[0], "uri": "media/x.jpg"}]   # 사진 주소 같은 모르는 칸은 받지 않음
    assert client.post("/import/instagram/preview", headers=H1, json={"posts": bad}).status_code == 422


def test_pick_n_then_same_zip_again_adds_nothing(client, env):  # noqa: F811
    client.headers.update(H1)
    pv, sent = script.import_zip(client, fx.zip_bytes(), 2)
    assert len(sent) == 2 and all(k == "result" for _, k, _ in sent)
    # 최근 2편을 오래된 것부터 보냄(다짐 · 질문 상태가 글 순서대로 바뀌게)
    assert [p["ref"] for p, _, _ in sent] == [pv["posts"][1]["ref"], pv["posts"][0]["ref"]]
    with env.repo.session(U1) as s:
        rows = s.rows("entries")
    assert len(rows) == 2 and {r["source"] for r in rows} == {"지난 글 묶음"}
    got = {d["title"]: d for _, _, d in sent}
    series = got["3/28 동아리 해커톤 (1)"]
    assert (series["day"], series["day_basis"], series["written_at"][:16]) == ("2026-03-28", "확실", "2026-03-29T01:20")
    # 같은 ZIP 을 전부 다시: 이미 가져온 2편은 '이미 가져옴', 나머지 4편만 새로
    pv2, sent2 = script.import_zip(client, fx.zip_bytes())
    assert [p["imported"] for p in pv2["posts"]] == [True, True, False, False, False, False] and len(sent2) == 4
    # 같은 ZIP 세 번째(화면이 표시를 무시하고 다 보내도): 새 기록 0편, Studio 도 다시 안 부름
    calls = env.fake.calls["record"]
    again = [script.send(client, script.body(p)) for p in pv2["posts"]]
    assert all(k == "result" and d["duplicate"] for k, d in again)
    with env.repo.session(U1) as s:
        assert len(s.rows("entries")) == 6
    assert env.fake.calls["record"] == calls
    assert all(script.preview(client, fx.zip_bytes())["posts"][i]["imported"] for i in range(6))


def test_max_posts_knob(client, env, monkeypatch):  # noqa: F811
    client.headers.update(H1)
    monkeypatch.setattr(config, "IMPORT_MAX_POSTS", 1)
    _, sent = script.import_zip(client, fx.zip_bytes())   # '전부'를 골라도 손잡이만큼
    assert len(sent) == 1


def test_four_inputs_script(client, env):  # noqa: F811
    """입력 4종(ZIP · MD · TXT · 직접 쓰기)이 끝까지 — 미리보기 배포에서는 같은 run()을 --base 로 돌린다."""
    client.headers.update(H1)
    rows, checks = script.run(client, n_zip=2)
    assert all(checks.values()), checks
    assert [r["input"] for r in rows] == ["인스타 ZIP", "인스타 ZIP", "MD 파일", "TXT 파일", "직접 쓰기"]
    md, txt = rows[2], rows[3]
    assert (md["source"], md["day"], md["day_basis"]) == ("텍스트", "2026-04-02", "확실")   # 파일 이름 속 날짜
    assert txt["day"] == "2026-04-03" and rows[4]["source"] == "텍스트"
