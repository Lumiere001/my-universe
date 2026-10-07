"""하늘 데모 시드(메모리 저장소, 외부 호출 없음): 사람이 그 이름이 나온 행성에 이어지고, 시드한 글은 하루 글 수에 들지 않는다."""
from app.core import llm, seed  # noqa: F401  (llm 을 먼저: safety ↔ llm 순환 import 순서)
from app.repository import MemRepo, diary, views
from tests.test_graph_flow import U1, env  # noqa: F401  (env 픽스처: 암호화 키)


def test_demo_people_linked_and_not_counted(env):  # noqa: F811
    repo = MemRepo()
    n = seed.demo(repo, U1)
    with repo.session(U1) as s:
        texts = [f"{e['data']['title']}\n{e['data']['text']}" for e in diary.entries(s)]
        people = {p["name"]: p for p in views.universe(s)["people"]}
        assert n == 29 and set(seed.DEMO_PEOPLE) <= set(people)
        for name in seed.DEMO_PEOPLE:
            assert len(people[name]["planets"]) == sum(name in t for t in texts) > 0
        assert diary.processed_today(s) == set()
    seed.wipe(repo, U1)
    assert not [r for rows in repo.store.tables.values() for r in rows if r.get("user_id") == U1]
    assert repo.vectors.get(U1) == {}
