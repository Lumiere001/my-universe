"""WS18 사진(손글씨) 입력: POST /photo/read(저장 0건 · 형식 · 크기 · 동의) → 고친 글로 POST /diary/stream(source=사진).
사진은 tools/photo_samples.py 로 만든 가상 손글씨(지호, 지어낸 글). Upstage 글자 읽기는 가짜 httpx, Studio · Solar 는 FakeUpstage."""
import copy
import json
from html import escape
from pathlib import Path

import httpx
import pytest

from app.api import upload
from app.core import config
from app.service import ocr
from tests.test_api_flow import H1, H2, U2, client, events  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import NAMES, U1, env  # noqa: F401  (env 픽스처)
from tools.photo_samples import PAGES

PHOTOS = Path(__file__).parent / "fixtures" / "photos"
# 실제 document-parse 응답(가상 사진 jiho-1012-p1, 2026-10-28, 단어 목록만 뺌)
DP = json.loads((Path(__file__).parent / "fixtures" / "dp" / "jiho-1012-p1.json").read_text())
ONE, P1, P2, HEIC = (PHOTOS / n for n in ("jiho-1010.jpg", "jiho-1012-p1.jpg", "jiho-1012-p2.jpg", "jiho-1010.heic"))
# 실제 Upstage ocr 이 가상 사진에서 읽은 것과 같은 모양(2026-10-14 측정: 두 쪽째 '알람'을 '일람'으로 읽음, 줄 끝 빈칸)
READ = {ONE.read_bytes(): PAGES[ONE.name], HEIC.read_bytes(): PAGES[ONE.name], P1.read_bytes(): PAGES[P1.name],
        P2.read_bytes(): PAGES[P2.name].replace("알람", "일람").replace(".\n", ". \n"),
        b"\xff\xd8\xff-crisis": "요즘 너무 지쳐서 죽고 싶다는 생각이 든다."}   # 가짜 jpg(앞 바이트만)


def dp_body(text):
    """document-parse 가 줄 공책을 읽는 모양(DP 처럼): 표 하나, 줄 = 행, 왼쪽 여백 = 빈 칸, 아래 빈 행. text 는 마크다운 표."""
    rows = "".join(f"<tr><td></td><td>{escape(x)}</td></tr>" for x in [*text.splitlines(), "", ""])
    return {"api": "2.0", "usage": {"pages": 1},
            "elements": [{"id": 0, "page": 1, "category": "table",
                          "content": {"html": f"<table><tbody>{rows}</tbody></table>", "text": "|  | 마크다운 표 |"}}]}


class FakeOcr:
    """httpx.post 대신: 받은 사진 바이트 · 폼을 남기고, 사진마다 정해 둔 글을 돌려준다."""

    def __init__(self):
        self.calls, self.status = [], [200]

    def __call__(self, url, data, files, headers, timeout):
        self.calls.append({"url": url, "form": data, "bytes": files["document"][1], "mime": files["document"][2]})
        st = self.status.pop(0) if len(self.status) > 1 else self.status[0]
        text = READ.get(files["document"][1], "")
        body = {} if st != 200 else {"text": text, "numBilledPages": 1, "stored": False} if data["model"] == "ocr" \
            else dp_body(text)
        return httpx.Response(st, json=body, request=httpx.Request("POST", url))


@pytest.fixture
def fake_ocr(monkeypatch):
    f = FakeOcr()
    monkeypatch.setattr(ocr.httpx, "post", f)
    monkeypatch.setattr(ocr.time, "sleep", lambda s: None)
    monkeypatch.setattr(config, "UPSTAGE_API_KEY", "test-key")
    return f


def read(client, path_or_bytes, h=H1):  # noqa: F811
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else path_or_bytes.read_bytes()
    return client.post("/photo/read", headers={**h, "Content-Type": "application/octet-stream"}, content=data)


def _dump(env):  # noqa: F811
    return json.dumps({t: [{k: (v.hex() if isinstance(v, bytes) else str(v)) for k, v in r.items()} for r in rows]
                       for t, rows in env.repo.store.tables.items()}, ensure_ascii=False)


def test_kind_by_bytes():
    """형식은 앞 바이트로(이름 · Content-Type 은 안 믿음): jpg · png · 아이폰 heic 만."""
    assert [ocr.kind(p.read_bytes()) for p in (ONE, HEIC)] == ["jpg", "heic"]
    assert ocr.kind(b"\x89PNG\r\n\x1a\n" + b"\0" * 20) == "png"
    for bad in (b"GIF89a....", b"%PDF-1.7", b"\x00\x00\x00\x1cftypavif", "일기".encode(), b""):
        assert ocr.kind(bad) is None
    assert ocr.tidy("  2026. 10. 10. 토 \n\n 오늘은  \n") == "2026. 10. 10. 토\n오늘은"


def test_read_photo_returns_text_and_keeps_nothing(client, env, fake_ocr):  # noqa: F811
    """사진 → 읽은 글만 돌려줌. 서버에 이미지 저장 0건(DB 그대로), 로그에 글 · 이름 · 사진 없음, Upstage 에는 사진 바이트 그대로 한 번."""
    kept = lambda: {t: rows for t, rows in copy.deepcopy(env.repo.store.tables).items() if rows}   # noqa: E731
    before = kept()
    r = read(client, ONE)
    assert r.status_code == 200 and r.json() == {"text": PAGES[ONE.name]}
    assert kept() == before                       # 기록 · 사진 · 읽은 글 어느 것도 저장 안 함
    (call,) = fake_ocr.calls
    assert call["bytes"] == ONE.read_bytes() and call["mime"] == "image/jpeg"
    assert call["form"] == {"model": "document-parse", "ocr": "force", "output_formats": '["html", "text"]'}   # 기본 = DP
    assert call["url"] == f"{config.UPSTAGE_BASE_URL}/document-digitization"
    logs = "".join(p.read_text() for p in env.logs.glob("*.log"))
    assert '"what": "upstage_ocr"' in logs and '"model": "document-parse"' in logs and '"est_usd": 0.01' in logs
    assert not [w for w in (*NAMES, "도서관", "복습") if w in logs] and "ffd8ff" not in logs
    # 아이폰 HEIC 는 그대로(Upstage 가 읽음)
    assert read(client, HEIC).json()["text"] == PAGES[ONE.name] and fake_ocr.calls[-1]["mime"] == "image/heic"


def test_dp_table_becomes_lines():
    """줄 공책은 DP 에서 표 하나로 옴(그대로 text 는 마크다운 표, 글자 정확도 0.2~0.5) → 행마다 한 줄로 풀어 ocr 과 같은 글자."""
    assert DP["elements"][0]["category"] == "table" and DP["content"]["text"].startswith("|  | 10월 12일")
    got = ocr.tidy(ocr.dp_text(DP))
    assert got.splitlines()[0] == "10월 12일 월요일" and "|" not in got and "---" not in got
    assert "".join(got.split()) == "".join(PAGES[P1.name].split())   # 쪽 끝에서 넘어간 줄('고마웠 / 다.')만 사진대로 나뉨
    # 여러 요소: 응답 순서 그대로 · 머리말(공책 위 날짜 칸)은 남기고 꼬리말(쪽 번호)은 뺌 · 칸은 빈칸으로, 칸 안 <br> 은 줄바꿈 ·
    # &amp; 는 글자로 · 빈 행 · 빈 요소는 빠짐 · 닫는 </td> 가 빠져도 칸을 잃지 않음
    j = {"elements": [
        {"category": "header", "content": {"text": "Date 10/12"}},
        {"category": "paragraph", "content": {"text": "첫 문단"}},
        {"category": "table", "content": {"html": "<table><thead><tr><th>시간</th><th>한 일</th></tr></thead><tbody>"
                                                "<tr><td>9시</td><td>회의 &amp; 정리<br>점심</td></tr><tr><td></td><td></td></tr>"
                                                "<tr><td>3시<td>산책</tr></tbody></table>"}},
        {"category": "footer", "content": {"text": "- 12 -"}},
        {"category": "paragraph", "content": {}}]}
    assert ocr.tidy(ocr.dp_text(j)) == "Date 10/12\n첫 문단\n시간 한 일\n9시 회의 & 정리\n점심\n3시 산책"
    assert ocr.dp_text({}) == ""


def test_read_model_switch_by_env(client, env, fake_ocr, monkeypatch):  # noqa: F811
    """PHOTO_READ_MODEL=ocr 로 코드 안 고치고 되돌림(쪽당 $0.0015). 모르는 값이면 사진을 보내지 않고 503 설정 없음."""
    monkeypatch.setattr(config, "PHOTO_READ_MODEL", "ocr")
    assert read(client, ONE).json() == {"text": PAGES[ONE.name]}
    assert fake_ocr.calls[-1]["form"] == {"model": "ocr"}
    assert '"est_usd": 0.0015' in "".join(p.read_text() for p in env.logs.glob("*.log"))
    monkeypatch.setattr(config, "PHOTO_READ_MODEL", "document-parse-260930")
    r = read(client, ONE)
    assert (r.status_code, r.json()["error"]["code"]) == (503, "ocr_unconfigured") and len(fake_ocr.calls) == 1


@pytest.mark.parametrize("data,status,code", [
    (b"", 422, "photo_empty"),
    (b"GIF89a" + b"\0" * 100, 415, "photo_type"),
    (b"%PDF-1.7 ...", 415, "photo_type"),
    ("오늘의 일기".encode(), 415, "photo_type"),
])
def test_bad_files_get_kind_errors(client, env, fake_ocr, data, status, code):  # noqa: F811
    r = read(client, data)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)
    assert "jpg · png · heic" in r.json()["error"]["message"] or code == "photo_empty"
    assert not fake_ocr.calls                                     # 밖으로 안 나감


def test_too_big_stops_reading(client, env, fake_ocr, monkeypatch):  # noqa: F811
    """한도(기본 4.5MB)를 넘으면 413 + 친절한 말. Content-Length 가 없어도(나눠 보내기) 넘는 순간 멈춘다."""
    assert upload.MAX_BYTES == 4_500_000
    monkeypatch.setattr(upload, "MAX_BYTES", 1000)
    r = read(client, ONE)
    assert r.status_code == 413 and r.json()["error"]["code"] == "photo_too_big" and "4.5MB" in r.json()["error"]["message"]
    r = client.post("/photo/read", headers=H1, content=iter([ONE.read_bytes()[:600], ONE.read_bytes()[600:1200]]))
    assert r.status_code == 413
    assert not fake_ocr.calls


def test_upstage_errors_are_friendly(client, env, fake_ocr, monkeypatch):  # noqa: F811
    fake_ocr.status = [429, 429, 200]                              # 붐비면 두 번까지 다시 물음
    assert read(client, ONE).status_code == 200 and len(fake_ocr.calls) == 3
    fake_ocr.status = [429]
    r = read(client, ONE)
    assert (r.status_code, r.json()["error"]["code"]) == (502, "ocr_busy")
    fake_ocr.status = [500]
    r = read(client, ONE)
    assert (r.status_code, r.json()["error"]["code"]) == (502, "ocr_failed") and "읽지 못했어요" in r.json()["error"]["message"]

    def boom(*a, **k):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(ocr.httpx, "post", boom)
    assert read(client, ONE).json()["error"]["code"] == "ocr_failed"
    monkeypatch.setattr(config, "UPSTAGE_API_KEY", "")
    r = read(client, ONE)
    assert (r.status_code, r.json()["error"]["code"]) == (503, "ocr_unconfigured")


def test_needs_login_and_consent(client, env, fake_ocr):  # noqa: F811
    assert read(client, ONE, h={}).status_code == 401
    with env.repo.session(U2) as s:
        s.delete("consents")
    r = read(client, ONE, h=H2)
    assert (r.status_code, r.json()["error"]["code"]) == (403, "consent_required")
    assert not fake_ocr.calls                                     # 동의 전에는 사진이 밖으로 안 나감


def test_two_pages_then_fixed_text_flows_as_photo(client, env, fake_ocr):  # noqa: F811
    """두 쪽 사진을 순서대로 읽어 이어 붙임 → 사용자가 잘못 읽은 글자를 고침 → source=사진 으로 정리.
    글이 다루는 날 = 첫 줄 날짜(10월 12일, 확실). 정리 · 한마디 요청(Studio · Solar)에 실명 0건."""
    pages = [read(client, p).json()["text"] for p in (P1, P2)]
    assert "일람" in pages[1]                                      # 잘못 읽은 글자는 쓰기 칸에서 사용자가 고친다
    text = "\n".join(pages).replace("일람", "알람")
    assert text == "\n".join(PAGES[n] for n in (P1.name, P2.name)).replace(". \n", ".\n")
    r = client.post("/diary/stream", headers=H1, json={"text": text, "source": "사진", "written_at": "2026-10-14T21:00:00+09:00"})
    kind, res = events(r.text)[-1]
    assert kind == "result" and res["status"] == "done" and res["thoughts"]
    assert (res["source"], res["day"], res["day_basis"], res["day_check"]) == ("사진", "2026-10-12", "확실", False)
    sent = "\n".join(env.fake.sent)
    assert sent and not [n for n in NAMES if n in sent]          # 가명 관문: 정리 요청에 실명 0건
    assert "ffd8ff" not in _dump(env) and not [n for n in NAMES if n in _dump(env)]   # 사진 · 실명은 DB 에 평문으로 없음


def test_photo_without_date_is_upload_day_guess(client, env, fake_ocr):  # noqa: F811
    """첫 줄에 날짜가 없는 쪽(두 쪽째만): 올린 날 · 추정."""
    text = read(client, P2).json()["text"]
    r = client.post("/diary/stream", headers=H1, json={"text": text, "source": "사진", "written_at": "2026-10-14T21:00:00+09:00"})
    res = events(r.text)[-1][1]
    assert (res["source"], res["day"], res["day_basis"]) == ("사진", "2026-10-14", "추정")


def test_crisis_photo_gets_same_care(client, env, fake_ocr):  # noqa: F811
    """사진 길도 위기 판정이 같다(시험 단계: 평소 결과 + 위로 한마디 + 안부 한 줄)."""
    text = read(client, b"\xff\xd8\xff-crisis").json()["text"]
    r = client.post("/diary/stream", headers=H1, json={"text": text, "source": "사진"})
    res = events(r.text)[-1][1]
    assert res["crisis"] and res["thoughts"] and res["message"]["mode"] == "comfort" and res["message"]["check_in"]
