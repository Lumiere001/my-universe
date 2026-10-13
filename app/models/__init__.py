"""
app/models

요청 본문 검사(신뢰 경계). 글 길이 상한, 보기 값은 v8.json 에서 읽는다. 모르는 칸은 거부한다.
"""

import re
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import config
from app.core.ontology import choices


CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")   # NUL 등 제어 문자(줄바꿈 · 탭은 남김). NUL 은 Postgres 가 거부해 500


class In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def _no_control(cls, v):
        return CONTROL.sub("", v) if isinstance(v, str) else v


def _one_of(name, v, allow_none=True):
    if v is None and allow_none:
        return v
    if v not in choices(name):
        raise ValueError(f"{name} 보기 밖 값")
    return v


SOURCES = ("대화", "텍스트", "사진", "지난 글 묶음")   # 기록 출처(PRD §4.1 · §4.4)


class DiaryIn(In):
    text: str = Field(min_length=1, max_length=config.MAX_TEXT_CHARS)
    title: str = Field(default="", max_length=config.MAX_TITLE_CHARS)
    written_at: Optional[datetime] = None
    weather: Optional[str] = None
    source: Literal[SOURCES] = "텍스트"
    source_ref: Optional[str] = Field(default=None, max_length=200)   # 가져온 원본 표시(같은 원본 다시 가져오기 막기)
    day: Optional[date] = None                                         # 사용자가 고른 글이 다루는 날
    confirm: bool = False                                              # 요약 확인 뒤 저장(save 앞에서 멈춤, WS20). 대화는 늘 확인

    @field_validator("title")
    @classmethod
    def _one_line(cls, v):
        return " ".join(v.split())

    @field_validator("weather")
    @classmethod
    def _weather(cls, v):
        return _one_of("weather", v or None)


FEEDBACK_TARGETS = ("relation", "message", "vow", "question", "tension", "entry", "app", "weather")


class FeedbackIn(In):
    target: Literal[FEEDBACK_TARGETS]
    target_id: Optional[str] = Field(default=None, max_length=80)
    value: str
    text: Optional[str] = Field(default=None, max_length=500)

    @field_validator("value")
    @classmethod
    def _value(cls, v):
        return _one_of("feedback", v, allow_none=False)


class PersonIn(In):
    name: str = Field(min_length=1, max_length=30)
    nickname: str = Field(default="", max_length=60)
    relation: str = Field(default="", max_length=30)


class PersonPatch(In):
    name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    nickname: Optional[str] = Field(default=None, max_length=60)
    relation: Optional[str] = Field(default=None, max_length=30)


class AnswerIn(In):
    answer: Literal["같은 사람", "다른 사람", "사람 이름", "사람 이름 아님"]


class AspirationIn(In):
    now: str = Field(default="", max_length=500)
    want: str = Field(min_length=1, max_length=500)
    obstacle: str = Field(default="", max_length=500)
    if_then: str = Field(default="", max_length=500)
    values: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("values")
    @classmethod
    def _values(cls, v):
        return [_one_of("values", x, allow_none=False) for x in v]


class DayIn(In):
    day: date   # 글이 다루는 날(사용자가 고침)


class DeclineIn(In):
    mode: Literal["skip", "stop"]


class SettingsPatch(In):
    tone: Optional[str] = None
    fact_bomb_ack: Optional[bool] = None
    gentle_today: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    comfort_only_today: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    suggestions: Optional[Literal["적게", "보통", "많이"]] = None
    cross_links: Optional[Literal["숨김", "눌렀을 때", "항상"]] = None
    weather_ask: Optional[bool] = None
    keeper_name: Optional[str] = Field(default=None, min_length=1, max_length=12)   # 별지기 이름(화면에만 씀)

    @field_validator("tone")
    @classmethod
    def _tone(cls, v):
        return _one_of("tones", v)


##################################################
# 대화 · 요약 확인 (WS19 · WS20)
##################################################

ID = r"^[A-Za-z0-9_-]{1,80}$"


class TalkIn(In):
    from_entry: Optional[str] = Field(default=None, pattern=ID)   # '이 이야기 이어 하기': 그 기록을 첫 맥락으로


class TurnIn(In):
    text: str = Field(min_length=1, max_length=config.MAX_TEXT_CHARS)


class ThoughtFix(In):
    id: str = Field(pattern=r"^[A-Za-z0-9_>-]{1,120}$")
    kind: Optional[str] = None      # 생각 종류 고치기
    remove: bool = False            # 이 생각 빼기

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        return _one_of("kinds", v)


class ConfirmIn(In):
    summary: Optional[str] = Field(default=None, min_length=1, max_length=1000)   # 고친 요약 문장(안 고쳤으면 비움)
    fixes: list[ThoughtFix] = Field(default_factory=list, max_length=100)
    agreed: list[str] = Field(default_factory=list, max_length=101)                # 맞아요를 누른 항목('summary' · 생각 id)
