"""
embedder.py

Solar Embedding으로 "같은 이야기인가"만 잰다 (PRD §6.1).
같은 편/반대편은 관측 Agent가, 얼마나 움직였나는 긴장 축이 맡는다.

주제 낱말은 그대로 비교하면 어떤 두 낱말이든 0.70~0.87이 나온다(실측). 그래서 흔한 주제 낱말들의
평균 벡터를 빼고(중심 보정) 비교한다. 보정 뒤에는 같은 뜻 낱말이 0.38~0.52, 다른 주제는 0.21 이하.
"""

import json
import math

from openai import OpenAI

import config

client = OpenAI(api_key=config.UPSTAGE_API_KEY, base_url="https://api.upstage.ai/v1")


def embed(texts):
    texts = [t if t.strip() else "(빈 글)" for t in texts]
    out = []
    for i in range(0, len(texts), 100):  # 한 번에 100개까지
        r = client.embeddings.create(model=config.EMBEDDING_MODEL, input=texts[i:i + 100])
        out += [[round(x, 5) for x in d.embedding] for d in r.data]
    return out


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


REFERENCE_TOPICS = ["진로", "배움", "건강", "관계", "신앙", "학업", "리더십", "가족", "취업", "공부", "동아리", "공동체",
                    "습관", "돈", "사랑", "연애", "우정", "일", "직장", "여행", "취미", "운동", "감정", "자기계발", "시간",
                    "봉사", "교회", "학교", "미래", "꿈", "성장", "외로움", "휴식", "음식", "날씨", "독서", "글쓰기", "음악",
                    "영화", "정치", "사회", "환경", "건축", "게임", "스포츠", "종교", "철학", "과학", "기술", "경제"]
_CENTER = config.DATA_DIR / "ops" / f"topic_center_{config.EMBEDDING_MODEL}.json"
_center = None


def topic_center():
    global _center
    if _center is None:
        if _CENTER.exists():
            _center = json.loads(_CENTER.read_text())
        else:
            vecs = embed(REFERENCE_TOPICS)
            _center = [round(sum(c) / len(vecs), 6) for c in zip(*vecs)]
            _CENTER.parent.mkdir(parents=True, exist_ok=True)
            _CENTER.write_text(json.dumps(_center))
    return _center


def topic_cos(a, b):
    """중심 보정 코사인 (주제 낱말끼리 비교할 때)."""
    c = topic_center()
    return cos([x - m for x, m in zip(a, c)], [y - m for y, m in zip(b, c)])
