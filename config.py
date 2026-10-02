"""
config.py

나의 우주 — 환경설정과 판단 기준값
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

##################################################
# Upstage API · Studio Agents
##################################################

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")

RECORD_AGENT_ID = os.getenv("RECORD_AGENT_ID")
RECORD_CONFIG_ID = os.getenv("RECORD_CONFIG_ID", "1")

OBSERVE_AGENT_ID = os.getenv("OBSERVE_AGENT_ID")
OBSERVE_CONFIG_ID = os.getenv("OBSERVE_CONFIG_ID", "1")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "solar-embedding-2-passage")

##################################################
# Directories
##################################################

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"      # 정리된 기록 (records.json)
RESULT_DIR = BASE_DIR / "result"      # 관측 보고서, 우주 상태
RUNS_DIR = BASE_DIR / "runs"          # 실행 기록(원문 없음)과 캐시

VIRTUAL_ZIP = DATA_DIR / "virtual" / "instagram-virtual-haneul.zip"
DEMO_UNIVERSE = DATA_DIR / "demo" / "universe-haneul.json"

##################################################
# 판단 기준값 (PRD §8.4, 실험으로 조정)
##################################################

SAME_STORY_THETA = 0.75     # 생각끼리 같은 이야기 후보
NEW_HUB_THETA = 0.35        # 중심 보정 유사도가 이 값 미만이면 새 성운 (PRD 처음 값 0.6은 보정 전 기준이라 실측 후 조정)
PAST_LIMIT = 10             # 관측 Agent에 넣는 과거 생각 수 (E4)
CHANGE_MIN_DAYS = 7         # 바뀜: 시간 차 이상
TENSION_MAX_DAYS = 30       # 긴장: 시간 차 이내
VOW_WINDOW_DAYS = 30        # 다짐 어긋남
GOAL_CONFLICT_DAYS = 14     # 목표 충돌

##################################################
# 비용 (추정용, Studio 요금표 · 1쪽당)
##################################################

PRICE_PARSE = 0.01
PRICE_EXTRACT = 0.04        # Classify는 Beta 기간 무료

##################################################
# 공개 배포 보호 (크레딧 상한)
##################################################

MAX_JOBS_PER_SESSION = int(os.getenv("MAX_JOBS_PER_SESSION", "40"))
MAX_IMPORT_POSTS = int(os.getenv("MAX_IMPORT_POSTS", "10"))

# 디스크 캐시에는 추출 결과(인용 포함)가 남으므로 로컬 개발에서만 켠다. 공개 서버는 끈 채로 둔다.
DISK_CACHE = os.getenv("DISK_CACHE", "0") == "1"


def validate_config():
    missing = [k for k, v in {
        "UPSTAGE_API_KEY": UPSTAGE_API_KEY,
        "RECORD_AGENT_ID": RECORD_AGENT_ID,
        "OBSERVE_AGENT_ID": OBSERVE_AGENT_ID,
    }.items() if not v]
    if missing:
        raise ValueError("다음 환경변수가 설정되지 않았습니다.\n\n" + "\n".join(missing))
    for d in (OUTPUT_DIR, RESULT_DIR, RUNS_DIR):
        d.mkdir(parents=True, exist_ok=True)
