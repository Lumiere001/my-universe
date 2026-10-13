"""WS25 꾸미기(API 쪽): 설정의 우주 테마 · 별지기 모습. 기본값 = 예전 모습, 목록 밖 값은 422, 사용자끼리 섞이지 않음.
화면의 값 목록(components/universeLook.ts THEMES · KEEPER_LOOKS)과 백엔드 SettingsPatch 목록이 같고, 모습마다 그림 파일이 있는지 대조한다."""
import re
import typing
from pathlib import Path

from app.models import SettingsPatch
from tests.test_api_flow import H1, H2, client  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import env  # noqa: F401  (env 픽스처)

FRONT = Path(__file__).resolve().parents[1] / "infra" / "frontend"
LOOK_TS = (FRONT / "components" / "universeLook.ts").read_text(encoding="utf-8")


def _choices(field):
    return list(typing.get_args(typing.get_args(SettingsPatch.model_fields[field].annotation)[0]))


def test_defaults_are_old_look(client):  # noqa: F811
    st = client.get("/me", headers=H1).json()["settings"]
    assert (st["theme"], st["keeper_look"]) == ("밤하늘", "글자")


def test_pick_theme_and_keeper(client):  # noqa: F811
    r = client.patch("/settings", headers=H1, json={"theme": "오로라", "keeper_look": "고양이"})
    assert r.status_code == 200 and (r.json()["theme"], r.json()["keeper_look"]) == ("오로라", "고양이")
    st = client.get("/me", headers=H1).json()["settings"]
    assert (st["theme"], st["keeper_look"], st["tone"]) == ("오로라", "고양이", "다정하게")   # 다른 설정은 그대로
    assert client.get("/me", headers=H2).json()["settings"]["theme"] == "밤하늘"            # 남의 설정은 안 바뀜
    assert client.patch("/settings", headers=H1, json={"theme": "밤하늘"}).json()["keeper_look"] == "고양이"


def test_unknown_values_rejected(client):  # noqa: F811
    for body in ({"theme": "무지개"}, {"keeper_look": "용"}, {"theme": ""}, {"keeper_look": 3}):
        assert client.patch("/settings", headers=H1, json=body).status_code == 422, body
    assert client.get("/me", headers=H1).json()["settings"]["theme"] == "밤하늘"


def test_front_lists_match_backend():
    block = LOOK_TS.split("export const THEMES = {", 1)[1].split("} satisfies", 1)[0]
    themes = re.findall(r'^  "([^"]+)":', block, re.M)
    assert themes == _choices("theme") and themes[0] == "밤하늘"   # 첫 값 = 기본
    looks = re.findall(r'"([^"]+)"', re.search(r"KEEPER_LOOKS = \[(.*?)\]", LOOK_TS).group(1))
    assert looks == _choices("keeper_look") and looks[0] == "글자"
    svg = dict(re.findall(r'(\S+): "(\w+)"', re.search(r"KEEPER_SVG[^=]*= \{(.*?)\}", LOOK_TS).group(1)))
    assert sorted(svg) == sorted(looks[1:])
    for f in svg.values():
        text = (FRONT / "public" / "keeper" / f"{f}.svg").read_text(encoding="utf-8")
        assert text.startswith("<svg") and "<script" not in text   # 정적 그림만
