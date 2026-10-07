"""v8 온톨로지 읽기. 목록 · 정의는 v8.json 하나에만 적고 모두 여기서 읽는다."""
import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).with_name("v8.json")


@lru_cache(maxsize=1)
def load():
    """v8.json 을 한 번 읽어 캐시한다. 돌려받은 dict 는 고치지 않는다."""
    return json.loads(_PATH.read_text(encoding="utf-8"))


def choices(name):
    """보기 이름 목록. name 은 맨 위 목록(kinds · values · domains …) 또는 칸 key(kind · addressee …)."""
    o = load()
    items = o.get(name)
    if isinstance(items, list) and items and isinstance(items[0], dict) and "name" in items[0]:
        return [x["name"] for x in items]
    for f in o["record_fields"] + o["thought_fields"]:
        if f["key"] == name:
            if "choices_from" in f:
                return choices(f["choices_from"])
            if "choices" in f:
                return [x["name"] for x in f["choices"]]
    raise KeyError(f"닫힌 목록이 아님: {name}")


def is_valid(name, value):
    return value in choices(name)
