"""
WS18 시험용 가상 손글씨 일기장 사진(가상 인물 지호, 지어낸 글 — 실제 일기 아님)과 글자 읽기 측정.

    uv run --frozen --with pillow python tools/photo_samples.py make      # tests/fixtures/photos/ 에 jpg 3장 + heic 1장(macOS sips)
    uv run --frozen python tools/photo_samples.py measure [원장 ws]       # 유료(약 $0.046): ocr · document-parse 를 네 장에 1회씩, 원장에 한 줄

사진은 나눔손글씨(펜) 글꼴 + 줄 공책 배경(살짝 기울기 · 그림자 · 종이 결)으로 그린다.
"""

import json
import random
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tests" / "fixtures" / "photos"
LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")

# (파일 이름, 쪽 글). 두 쪽짜리 하나 포함. 첫 줄 날짜는 G2(글이 다루는 날) 확인용.
PAGES = {
    "jiho-1010.jpg": "2026. 10. 10. 토\n"
                     "오늘 도서관에서 민준이랑 시험 공부를 했다.\n"
                     "혼자 할 때보다 덜 지루했다.\n"
                     "서윤 선배가 빌려준 노트가 큰 도움이 됐다.\n"
                     "다음 주까지 매일 한 단원씩 복습하겠다.",
    "jiho-1012-p1.jpg": "10월 12일 월요일\n"
                        "아침에 늦잠을 자서 축제 부스 회의에 늦었다.\n"
                        "민준이가 대신 자리를 맡아 줘서 미안하고 고마웠다.\n"
                        "나는 왜 자꾸 중요한 날에 늦을까.",
    "jiho-1012-p2.jpg": "저녁에는 서윤 선배와 부스 도안을 다시 그렸다.\n"
                        "같이 하니까 생각보다 빨리 끝났다.\n"
                        "앞으로 회의 전날에는 알람을 두 개 맞추겠다.",
}
HEIC = "jiho-1010.heic"   # jiho-1010.jpg 를 sips 로 바꾼 것(아이폰 사진 형식)


def _font(size):
    from PIL import ImageFont
    for p in [*Path("/System/Library/AssetsV2").glob("*/*/AssetData/NanumScript.ttc"),
              Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf")]:
        if p.exists():
            return ImageFont.truetype(str(p), size)   # NanumScript.ttc 0번 = 나눔손글씨 펜
    sys.exit("한글 글꼴을 찾지 못했어요.")


def draw(text, seed):
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    w, h, top, gap, margin = 1500, 2000, 260, 110, 210
    page = Image.new("RGB", (w, h), (247, 242, 228))
    d = ImageDraw.Draw(page)
    for y in range(top, h - 80, gap):                      # 줄 공책: 파란 가로줄 + 빨간 여백 줄
        d.line([(0, y), (w, y)], fill=(170, 195, 225), width=3)
    d.line([(margin - 30, 0), (margin - 30, h)], fill=(225, 150, 150), width=3)
    font, row = _font(80), 0
    for line in text.splitlines():
        x = margin
        for ch in line:                                   # 글자마다 높이 · 기울기를 조금씩 흔들어 손글씨처럼
            if x > w - 140:                               # 쪽 끝에 닿으면 다음 줄로
                x, row = margin, row + 1
            g = Image.new("RGBA", (130, 130), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((10, 10), ch, font=font, fill=(35, 40, 70, 255))
            g = g.rotate(rnd.uniform(-4, 4), resample=Image.BICUBIC)
            page.paste(g, (int(x), int(top + row * gap - 112 + rnd.uniform(-5, 5))), g)
            x += font.getlength(ch) * rnd.uniform(0.95, 1.05) + (8 if ch == " " else 1)
        row += 1
    page = page.rotate(rnd.uniform(-1.5, 1.5), resample=Image.BICUBIC, expand=False, fillcolor=(90, 80, 70))
    shade = Image.linear_gradient("L").rotate(90).resize((w, h))   # 왼쪽이 조금 어두운 폰 사진 그림자
    page = Image.composite(page, Image.new("RGB", (w, h), (150, 140, 125)), shade.point(lambda v: 255 - v // 4))
    noise = Image.effect_noise((w, h), 18).convert("RGB")
    page = Image.blend(page, noise, 0.06).filter(ImageFilter.GaussianBlur(0.6))
    return page


def make():
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, text) in enumerate(PAGES.items()):
        draw(text, seed=i).save(OUT / name, "JPEG", quality=80)
    subprocess.run(["sips", "-s", "format", "heic", str(OUT / "jiho-1010.jpg"), "--out", str(OUT / HEIC)],
                   check=True, capture_output=True)
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size)


def _accuracy(got, want):
    """글자 정확도 = 1 - 편집 거리 / 정답 길이(띄어쓰기 · 줄바꿈 무시)."""
    a, b = "".join(got.split()), "".join(want.split())
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return round(1 - prev[-1] / max(len(b), 1), 3)


def measure(ws="WS18"):
    """유료: 네 장을 ocr · document-parse 로 한 번씩(쪽당 $0.0015 · $0.01). DP 는 한 응답으로 그대로(content.text) · 풀기(dp_text)를
    함께 잰다. 원장에는 이번 실행을 한 줄로."""
    from app.service import ocr
    calls, usd = 0, 0.0
    try:
        for model in ("ocr", "document-parse"):
            for name in (*PAGES, HEIC):
                t0 = time.time()
                j = ocr.ask((OUT / name).read_bytes(), model)
                sec = round(time.time() - t0, 1)
                calls, usd = calls + 1, usd + ocr.PRICE_PER_PAGE[model]
                got = {"ocr": j.get("text")} if model == "ocr" else \
                    {"document-parse 그대로": (j.get("content") or {}).get("text"), "document-parse 풀기": ocr.dp_text(j)}
                for how, text in got.items():
                    text = ocr.tidy(text)
                    print(json.dumps({"how": how, "file": name, "seconds": sec, "est_usd": ocr.PRICE_PER_PAGE[model],
                                      "accuracy": _accuracy(text, PAGES[name.replace(".heic", ".jpg")]),
                                      "first_line": text.splitlines()[0] if text else ""}, ensure_ascii=False))
    finally:
        if calls:
            with LEDGER.open("a") as f:
                f.write(json.dumps({"ts": datetime.now().astimezone().isoformat(timespec="seconds"), "ws": ws,
                                    "what": f"글자 읽기 측정 ocr · document-parse(그대로 · 풀기) 가상 손글씨 {len(PAGES) + 1}장",
                                    "calls": calls, "est_usd": round(usd, 4)}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    {"make": make, "measure": measure}[sys.argv[1] if len(sys.argv) > 1 else "make"](*sys.argv[2:])
