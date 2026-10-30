"""작은 별 묶음(rules.groups · graph.group_stars): 같은 고민끼리 묶어 묶음 머리 이름으로 보이고, 작은 별은 지우지 않는다."""
import json

from app.agents import graph
from app.core import config
from app.repository import diary, edit, views
from app.service.rules import groups
from tests.test_graph_flow import DAY1, NAMES, U1, env, write  # noqa: F401


def star(i, name, records, sun="삶의 성취", pin=None):
    return {"id": i, "name": name, "sun": sun, "records": records, "quotes": [f"{name} 예"], "pin": pin}


def test_parse_groups_fixes_missing_duplicate_and_bad_numbers():
    assert groups.parse_groups('설명 {"groups": [[1, 3], [3, 9, "x"]]} 끝', 4) == [[0, 2], [1], [3]]
    assert groups.parse_groups("답이 JSON 이 아님", 2) == [[0], [1]]
    assert groups.parse_suns('{"suns": [{"group": 2, "sun": "인간관계"}, {"group": 1, "sun": "없는 해"}]}', 2,
                             [("커리어", ""), ("인간관계", "")]) == [None, "인간관계"]


def test_apply_head_is_most_written_star_and_pin_wins():
    stars = [star("a", "대본 연습", 1), star("b", "영어 녹음", 5), star("c", "도현 답장", 3, "관계", pin=True)]
    got = groups.apply(stars, [[0, 1], [2]], ["커리어", "커리어"])
    assert got["a"] == got["b"] == {"head": "b", "sun": "커리어"}
    assert got["c"] == {"head": "c", "sun": "관계"}   # 사용자가 옮긴 별은 사용자가 고른 해


def test_apply_keeps_declined_pair_apart():
    stars = [star("a", "첫째", 2), star("b", "둘째", 1), star("c", "셋째", 1)]
    got = groups.apply(stars, [[0, 1, 2]], [None], declined={"a>b"})
    assert got["a"]["head"] == got["c"]["head"] == "a" and got["b"]["head"] == "b"


def test_two_domain_sun_choices(monkeypatch):
    monkeypatch.setattr(config, "ONTOLOGY_PROFILE", "two")
    assert [n for n, _ in groups.sun_choices(["독서"])] == ["커리어", "인간관계", "그 밖", "독서"]
    monkeypatch.setattr(config, "ONTOLOGY_PROFILE", "")
    assert len(groups.sun_choices()) == 9


def _topics_by_title(env, monkeypatch, table):
    first = env.fake._record

    def record(html):
        d = first(html)
        n = next((v for k, v in table.items() if k in html), "기타 주제")
        for t in d["thoughts"]:
            t["topic"] = [n]
        return d
    monkeypatch.setattr(env.fake, "_record", record)


def test_group_stars_shows_head_and_keeps_small_stars(env, monkeypatch):
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록", "셋째": "걷기 기록"})
    env.fake.group_answer = [[1, 2]]
    env.fake.sun_answer = [{"group": 1, "sun": "건강"}]
    write(env, U1, "첫날", DAY1[1], "2026-10-01T22:00:00+09:00")
    write(env, U1, "둘째", "걷기를 적었다. 민준이랑 걸었다.", "2026-10-02T22:00:00+09:00")
    eid, _, r = write(env, U1, "셋째", "걷기를 또 적었다.", "2026-10-03T22:00:00+09:00")
    with env.repo.session(U1) as s:
        stars = {x["name"]: x for x in diary.stars(s)}
        u = views.universe(s)
        ins = views.insight(s)
        sun = {x["id"]: x["name"] for x in diary.suns(s)}
        thought_suns = {sun[t["sun_id"]] for t in diary.thoughts(s)}
    assert set(stars) == {"아침 걷기", "걷기 기록"}                       # 작은 별은 지우지 않는다
    # 둘째 글 뒤 묶을 때 둘 다 1편 → 먼저 만든 별이 머리. 셋째 글은 새 별이 없어 다시 묶지 않는다(머리 이름이 흔들리지 않게)
    assert stars["걷기 기록"].get("group") == stars["아침 걷기"]["id"] and not stars["아침 걷기"].get("group")
    assert [x["name"] for x in u["stars"]] == ["아침 걷기"] and len(u["planets"]) == 3
    assert thought_suns == {"건강"}                                       # 묶음이 고른 해로 옮김
    assert [x["name"] for x in ins["suns"][0]["stars"]] == ["아침 걷기"]
    assert {t["topic"] for t in r["thoughts"]} == {"아침 걷기"}
    sent = "\n".join(env.fake.sent)
    assert "작은 별 목록" in sent and not [n for n in NAMES if n in sent]   # 묶기 요청도 가명으로


def test_move_and_merge_act_on_whole_group(env, monkeypatch):
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록", "셋째": "민준과 대화"})
    env.fake.group_answer = [[1, 2], [3]]
    for i, title in enumerate(("첫날", "둘째", "셋째"), 1):
        write(env, U1, title, "걷기를 적었다.", f"2026-10-0{i}T22:00:00+09:00")
    with env.repo.session(U1) as s:
        st = {x["name"]: x for x in diary.stars(s)}
        head = diary.star_heads(diary.stars(s))[st["걷기 기록"]["id"]]["id"]
        to = diary.ensure_sun(s, "관계")
        edit.move_star(s, head, to)
        assert {x["sun_id"] for x in diary.stars(s) if x["name"] != "민준과 대화"} == {to}
        assert all(x.get("pin") for x in diary.stars(s) if x["name"] != "민준과 대화")
        edit.merge_stars(s, head, st["민준과 대화"]["id"])
        assert [x["name"] for x in diary.stars(s)] == ["민준과 대화"]   # 사람이 합치면 묶음 전체를 실제로 합친다


def test_regroup_once_after_mode_change(env, monkeypatch):
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록"})
    write(env, U1, "첫날", DAY1[1], "2026-10-01T22:00:00+09:00")
    write(env, U1, "둘째", "걷기를 적었다.", "2026-10-02T22:00:00+09:00")
    monkeypatch.setattr(config, "ONTOLOGY_PROFILE", "two")
    env.fake.group_answer, env.fake.sun_answer = [[1, 2]], [{"group": 1, "sun": "커리어"}]
    before = env.fake.calls["chat"]
    assert graph.ensure_groups(env.repo, U1) == {"stars": 2, "groups": 1, "moved": 2}   # 기존 해 옮기기
    assert graph.ensure_groups(env.repo, U1) is None and env.fake.calls["chat"] == before + 2   # 한 번만
    with env.repo.session(U1) as s:
        sun = {x["id"]: x["name"] for x in diary.suns(s)}
        assert {sun[t["sun_id"]] for t in diary.thoughts(s)} == {"커리어"}
        assert diary.profile(s)[0]["groups_profile"] == "two"
        assert len(views.universe(s)["stars"]) == 1 and len(views.universe(s)["stars"][0]["members"]) == 1   # 머리 하나, 묶인 작은 별 하나


def test_observer_sees_group_names_before_save(env, monkeypatch):
    """묶기는 관측 전에 돈다: 새 이름의 생각도 지난 생각 고르기 · 관측 Agent · 관계 규칙에는 묶음 이름으로 간다(판단형 = 같은 묶음 안)."""
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록"})
    env.fake.group_answer = [[1, 2]]
    seen = []
    real = graph.tools.run_observe_agent

    def spy(day, today, past, asp, people, rejected=()):
        seen.append(({t["topic"] for t in today}, {t["topic"] for t in past}))
        return real(day, today, past, asp, people, rejected)
    monkeypatch.setattr(graph.tools, "run_observe_agent", spy)
    write(env, U1, "첫날", DAY1[1], "2026-10-01T22:00:00+09:00")
    _, _, r = write(env, U1, "둘째", "걷기를 적었다.", "2026-10-02T22:00:00+09:00")
    assert seen[-1] == ({"아침 걷기"}, {"아침 걷기"})
    with env.repo.session(U1) as s:
        assert {t["topic"] for t in diary.thoughts(s)} == {"아침 걷기", "걷기 기록"}   # 저장은 기록 Agent 가 낸 이름 그대로
    assert r["relations"]   # 같은 묶음이라 이어짐이 남음


def test_input_shows_last_groups_and_old_groups_never_merge():
    """일관성(2026-10-30): 지난 묶음을 번호로 보여 주고, Solar 가 지난 묶음 둘을 한 묶음에 넣어도 코드가 다시 나눈다(눈덩이 방지)."""
    stars = [{**star("a", "아침 걷기", 3, "커리어"), "prev": "a"}, {**star("b", "걷기 기록", 1, "커리어"), "prev": "a"},
             star("c", "새 별", 1, "인간관계"), {**star("d", "엄마 통화", 2, "인간관계"), "prev": "d"}]
    text = groups.group_input(stars)
    assert "(3편 · 지난 묶음 1)" in text and "(1편 · 지난 묶음 1)" in text and "(2편 · 지난 묶음 2)" in text
    assert "새 별 (1편)" in text and "지난 묶음끼리는 합치지 않는다" in groups.GROUP_SYSTEM
    assert groups.keep_old_apart(stars, [[0, 1, 2, 3]]) == [[0, 1, 2], [3]]   # 새 별은 큰 지난 묶음(4편)에
    assert groups.keep_old_apart(stars, [[0, 2], [1], [3]]) == [[0, 2], [1], [3]]   # 나누는 것은 Solar 몫, 코드는 합침만 막는다


def test_regroup_carries_last_groups_until_stars_grow(env, monkeypatch):
    """지난 묶음을 이어 받다가, 작은 별이 지난번 새로 묶었을 때의 1.5배가 되면 한 번 새로 묶는다(이른 판단 바로잡기)."""
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록", "셋째": "엄마 통화", "넷째": "동생 통화"})
    env.fake.group_answer = [[1, 2]]
    seen, real = [], graph.tools.group_stars

    def spy(stars, people, custom=()):
        seen.append({st["name"]: st.get("prev") for st in stars})
        return real(stars, people, custom)
    monkeypatch.setattr(graph.tools, "group_stars", spy)
    for i, title in enumerate(("첫날", "둘째", "셋째", "넷째"), 1):
        write(env, U1, title, "걷기를 적었다.", f"2026-10-0{i}T22:00:00+09:00")
    assert not any(seen[0].values()) and not any(seen[1].values())   # 별 2개(처음) · 3개(2의 1.5배) → 새로 묶기
    head = seen[2]["아침 걷기"]
    assert head and seen[2]["걷기 기록"] == head and seen[2]["엄마 통화"] is None and seen[2]["동생 통화"] is None   # 별 4개 → 이어 받기
    with env.repo.session(U1) as s:
        assert diary.profile(s)[0]["groups_fresh_at"] == 3


def test_detach_star_leaves_group_and_stays_apart(env, monkeypatch):
    """작은 별 떼어 내기(2026-10-30): 묶음에서 빠지고, 같은 묶음의 별과는 다시 묶지 않는다(거절 짝). 머리를 떼면 남은 별이 새 머리."""
    _topics_by_title(env, monkeypatch, {"첫날": "아침 걷기", "둘째": "걷기 기록", "셋째": "걷기 친구"})
    env.fake.group_answer = [[1, 2, 3]]
    for i, title in enumerate(("첫날", "둘째", "셋째"), 1):
        write(env, U1, title, "걷기를 적었다.", f"2026-10-0{i}T22:00:00+09:00")
    with env.repo.session(U1) as s:
        st = {x["name"]: x for x in diary.stars(s)}
        head = st["아침 걷기"]["id"]
        u = views.universe(s)
        assert {m["name"] for m in next(x for x in u["stars"] if x["id"] == head)["members"]} == {"걷기 기록", "걷기 친구"}
        assert edit.detach_star(s, st["걷기 친구"]["id"])["name"] == "걷기 친구"
        st = {x["name"]: x for x in diary.stars(s)}
        assert not st["걷기 친구"].get("group") and st["걷기 기록"]["group"] == head
        assert edit.pair_id(st["걷기 친구"]["id"], head) in edit.declined(s)
        edit.detach_star(s, head)                                         # 머리를 떼면 남은 별이 새 머리
        st = {x["name"]: x for x in diary.stars(s)}
        assert not st["아침 걷기"].get("group") and not st["걷기 기록"].get("group")
        assert edit.detach_star(s, st["걷기 기록"]["id"]) is None          # 혼자인 별은 뗄 수 없음
        assert sum(f["value"] == "떼어 냄" for f in s.rows("feedback")) == 2
    write(env, U1, "넷째", "걷기를 적었다.", "2026-10-04T22:00:00+09:00")   # 다음 묶기가 같은 셋을 다시 묶으려 해도
    with env.repo.session(U1) as s:
        heads = diary.star_heads(diary.stars(s))
        st = {x["name"]: x for x in diary.stars(s)}
        assert heads[st["걷기 친구"]["id"]]["id"] != heads[st["아침 걷기"]["id"]]["id"]
