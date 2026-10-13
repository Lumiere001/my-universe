"""
가상 인물 도담(골든셋 p_student, 대학생)의 인스타그램 '내 정보 다운로드' ZIP. 모두 지어낸 글이다(실제 일기 아님).

담은 사례: 깨진 한글(UTF-8 바이트를 latin-1 글자로 적은 인스타 내보내기 그대로), 이어 쓴 게시물 2개(하나로 묶임),
제목 속 날짜(1월에 올린 12/31 일기 = 지난해), 제목 날짜 없는 글(게시일 추정), 사진만 있는 게시물(빠짐),
예전 형식(캡션이 media[0] 안에), 한 줄 글('날'로 끝남 — 깨진 바이트 A0 이 공백으로 지워지지 않는지).

    uv run --frozen python -m tests.fixtures.instagram_virtual   # → 화면 예시 ZIP(infra/frontend/public/samples/) 다시 만들기
"""

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ZIP = Path(__file__).resolve().parents[2] / "infra" / "frontend" / "public" / "samples" / "instagram-virtual-dodam.zip"
POSTS_JSON = "your_instagram_activity/content/posts_1.json"
KST = ZoneInfo("Asia/Seoul")


def _ts(s):
    return int(datetime.fromisoformat(s).replace(tzinfo=KST).timestamp())


# (게시 시각 KST, 캡션, 형식) — 형식: "top" = 게시물 title, "media" = media[0].title(예전 형식)
CAPTIONS = [
    ("2026-01-02T00:30", "12/31 올해 마지막 날\n윤재랑 기숙사에서 컵라면 먹으면서 한 해 돌아봄 ㅋㅋ\n"
                         "올해는 생각보다 잘 버텼다. 내년엔 운동을 꾸준히 하겠다.", "top"),
    ("2026-03-03T23:10", "3/3 개강\n3학년 첫 수업. 알고리즘 교수님 진짜 빡세다 ㅋㅋ\n"
                         "그래도 이번 학기는 과제 미루지 않고 그날그날 하겠다.", "top"),
    ("2026-03-10T12:00", "", "top"),   # 사진만
    ("2026-03-20T22:00", "새벽 생각\n요즘 윤재가 말이 없어졌다. 먼저 물어볼까 하다가 그냥 잤다.\n내일은 꼭 밥 먹자고 해야지.", "top"),
    ("2026-03-22T21:30", "3/22 일요일\n오랜만에 본가 다녀옴. 반찬을 잔뜩 싸 왔다.\n집에 다녀오니까 마음이 좀 놓인다. 다음 달에도 한 번 가야겠다.",
     "media"),
    ("2026-03-25T23:50", "오늘은 그냥 아무것도 하기 싫은 날", "top"),
    ("2026-03-29T01:20", "3/28 동아리 해커톤 (1)\n하늘이가 팀장을 맡아 줘서 다행이었다.\n밤새 코드 짜다가 서버가 터졌다 ㅋㅋ\n(2)에서 이어짐 =>",
     "top"),
    ("2026-03-29T01:22", "(2) 이어서\n결국 새벽 다섯 시에 고쳤다. 혼자 붙잡고 있을 때보다 같이 보니까 금방 찾았다.\n"
                         "예전엔 남한테 묻는 게 민폐라고 생각했는데 이제는 아니다.", "top"),
]


def _broken(s):
    return s.encode("utf-8").decode("latin-1")   # 인스타 내보내기의 깨진 한글


def posts():
    out = []
    for i, (when, caption, form) in enumerate(CAPTIONS):
        ts = _ts(when)
        media = {"uri": f"media/posts/202603/dodam_{i:02d}.jpg", "creation_timestamp": ts, "title": ""}
        if form == "media":
            media["title"] = _broken(caption)
            out.append({"media": [media]})
        else:
            out.append({"media": [media], "title": _broken(caption), "creation_timestamp": ts})
    return out


def zip_bytes():
    """같은 내용이면 같은 바이트(시각 고정). posts_1.json 은 압축, 사진 자리는 그대로 저장."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("media/posts/202603/dodam_00.jpg", (2026, 4, 1, 0, 0, 0)), b"\xff\xd8\xff\xd9")
        info = zipfile.ZipInfo(POSTS_JSON, (2026, 4, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, json.dumps(posts(), ensure_ascii=True, indent=2))   # 인스타처럼 ì… 로 적음
    return buf.getvalue()


if __name__ == "__main__":
    ZIP.write_bytes(zip_bytes())
    print(ZIP, len(ZIP.read_bytes()), "bytes")
