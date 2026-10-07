"""
app/models

요청 본문 검사(신뢰 경계). 글 길이 상한, 보기 값은 v8.json 에서 읽는다. 모르는 칸은 거부한다.
"""

import re
from datetime import datetime
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


class DiaryIn(In):
    text: str = Field(min_length=1, max_length=config.MAX_TEXT_CHARS)
    title: str = Field(default="", max_length=config.MAX_TITLE_CHARS)
    written_at: Optional[datetime] = None
    weather: Optional[str] = None

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

    @field_validator("tone")
    @classmethod
    def _tone(cls, v):
        return _one_of("tones", v)
