"""llm.guard 실명 검사: 사용자 · 도구 입력만 보고, 코드가 쓴 시스템 글 · 고정 라벨에는 걸리지 않는다(가상 인물)."""
from types import SimpleNamespace

import pytest

from app.core import llm
from app.service.safety import RealNameLeak
from app.service.studio_format import record_html

PEOPLE = [{"name": "별", "nicknames": [], "relation": "동생"}, {"name": "솔", "nicknames": [], "relation": "친구"}]


@pytest.fixture
def sent(monkeypatch):
    out = []

    def create(**kw):
        out.append(kw)
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(llm, "client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    return out


def test_system_prompt_and_fixed_labels_do_not_trip_one_letter_names(sent):
    with llm.guard(PEOPLE):
        llm.chat([{"role": "system", "content": "너는 별지기다. 솔직하게 말한다."},
                  {"role": "user", "content": "[오늘 글]\n서아가 웃었다.\n\n[별지기 한마디]\n좋았겠다."}])
        llm.current().check(record_html("제목", "서아랑 놀았다.", ["진로"]), "studio_record")
    assert len(sent) == 1


@pytest.mark.parametrize("content", ["별이 웃었다.", "솔이랑 놀았다.", "[별지기 한마디]\n별이 고마워."])
def test_real_name_in_user_text_is_blocked(sent, content):
    with llm.guard(PEOPLE), pytest.raises(RealNameLeak):
        llm.chat([{"role": "system", "content": "규칙"}, {"role": "user", "content": content}])
    assert sent == []


def test_real_name_in_tool_input_is_blocked():
    with llm.guard(PEOPLE), pytest.raises(RealNameLeak):
        llm.current().check(record_html("제목", "별이랑 놀았다."), "studio_record")
