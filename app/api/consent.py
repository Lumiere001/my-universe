"""
app/api/consent.py

첫 로그인 동의(WS24). 화면 /consent 가 문구를 보여 주고, 여기는 판 번호와 동의 기록만 다룬다.
- GET /consent: 지금 판 · 다시 물어야 하는지 · 가장 최근 동의
- POST /consent: 필수 셋(필수 · 민감정보 · 만 14세 이상)이 모두 참일 때만 한 줄 덧붙인다(선택: 운영자 피드백 열람)
- check(s): 기록을 만드는 요청(일기 쓰기 · 이어 하기 → 외부 AI 로 나감)이 부른다. 동의가 없거나 옛 판이면 403.
  화면 가드만으로는 토큰으로 API 를 바로 부르는 길 · 동의 전에 열어 둔 탭을 못 막아서 서버에서도 막는다.
- operator_read(s): 운영 화면(WS22)이 피드백 원문을 풀어 보여도 되는 사용자인지.
"""

from fastapi import APIRouter, Depends

from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import In
from app.repository import diary

VERSION = "2026-10-13"   # 동의 문구 판. infra/frontend/app/consent · privacy · terms 문구를 바꾸면 올린다(모두 다시 물음)

router = APIRouter(tags=["동의"])


class ConsentIn(In):
    version: str
    required: bool
    sensitive: bool
    age14: bool
    operator_read: bool = False


def latest(s):
    r = s.rows("consents", order="created_at desc", limit=1)
    return r[0] if r else None


def needed(s):
    c = latest(s)
    return not c or c["version"] != VERSION


def check(s):
    if needed(s):
        raise ApiError(403, "consent_required", "먼저 이용 동의를 해 주세요.")


def operator_read(s):
    return not needed(s) and latest(s)["operator_read"]


def save(s, operator_read=False):
    s.insert("consents", {"id": diary.new_id("c"), "version": VERSION, "required": True, "sensitive": True, "age14": True,
                          "operator_read": operator_read, "created_at": diary.now()})


def _view(s):
    c = latest(s)
    return {"version": VERSION, "needed": needed(s),
            "agreed": c and {"version": c["version"], "operator_read": c["operator_read"], "at": diary.iso(c["created_at"])}}


@router.get("/consent", summary="지금 동의 판 · 다시 물어야 하는지 · 가장 최근 동의")
def get_consent(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return _view(s)


@router.post("/consent", summary="동의하기(필수 셋은 참이어야 함, 선택은 운영자 피드백 열람)")
def post_consent(body: ConsentIn, user=Depends(get_user), repo=Depends(get_repo)):
    if body.version != VERSION:
        raise ApiError(409, "consent_outdated", "동의 문구가 바뀌었어요. 화면을 새로 고쳐 다시 읽어 주세요.")
    if not body.age14:
        raise ApiError(403, "under_14", "만 14세 미만은 지금 쓸 수 없어요.")
    if not (body.required and body.sensitive):
        raise ApiError(422, "consent_missing", "필수 동의가 빠졌어요.")
    with repo.session(user["id"]) as s:
        save(s, body.operator_read)
        return _view(s)
