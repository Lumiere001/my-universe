"""PRD 그림 4장 (가이드 그림 스타일: 흰 바탕, 파스텔 카드, 번호 원, 선 아이콘, 남색 화살표).

    python tools/diagrams/make_diagrams.py   → tools/diagrams/out/*.html → 헤드리스 Chrome으로 PNG
"""
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

C = {  # (진한 색, 연한 바탕, 테두리)
    "blue": ("#2f6fe4", "#f2f7ff", "#a9c6f5"), "green": ("#2e9d57", "#f1fbf4", "#a6dbb8"),
    "purple": ("#7b52e0", "#f6f2ff", "#c7b5f3"), "orange": ("#ef7d1a", "#fff6ec", "#f6c48f"),
    "teal": ("#178f8a", "#eefaf9", "#9ad7d3"), "yellow": ("#d39a07", "#fffaea", "#f0d37c"),
    "pink": ("#e0457b", "#fff1f5", "#f3a9c2"), "gray": ("#5b6478", "#f6f7f9", "#cdd2dc"),
}
NAVY = "#33415c"

CSS = """
*{box-sizing:border-box}body{margin:0;background:#fff;font-family:Pretendard,'Apple SD Gothic Neo',sans-serif;color:#1e2638}
.c{position:absolute;border:2px solid;border-radius:18px;padding:16px 18px}
.num{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;color:#fff;font-weight:800;font-size:18px;margin-right:10px;flex:none}
.t{font-weight:800;font-size:21px;line-height:1.25}.en{font-size:13px;font-weight:600;opacity:.75;margin-top:2px}
.d{font-size:15.5px;line-height:1.5;color:#33415c}.ex{font-size:13.5px;color:#5b6478;line-height:1.45}
.head{display:flex;align-items:center}
.chip{display:inline-block;border:1.5px solid;border-radius:999px;padding:3px 10px;font-size:13.5px;margin:3px 4px 0 0;background:#fff;font-weight:600}
.tag{display:inline-block;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:800;margin-left:6px;vertical-align:middle}
h1{position:absolute;left:0;right:0;text-align:center;margin:0;font-size:40px;font-weight:800;color:#1e2a46}
.sub{position:absolute;left:0;right:0;text-align:center;font-size:19px;color:#5b6478}
svg.ar{position:absolute;left:0;top:0;pointer-events:none}
"""


def icon(name, col, s=64):
    p = {
        "doc_up": f'<rect x="12" y="6" width="32" height="42" rx="4" fill="#fff" stroke="#8a93a8" stroke-width="2.5"/><line x1="19" y1="18" x2="37" y2="18" stroke="#8a93a8" stroke-width="2.5"/><line x1="19" y1="26" x2="37" y2="26" stroke="#8a93a8" stroke-width="2.5"/><line x1="19" y1="34" x2="30" y2="34" stroke="#8a93a8" stroke-width="2.5"/><circle cx="44" cy="46" r="13" fill="{col}"/><path d="M44 52v-12M38.5 45l5.5-5.5 5.5 5.5" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round"/>',
        "doc_code": f'<rect x="12" y="6" width="38" height="50" rx="5" fill="#fff" stroke="{col}" stroke-width="2.8"/><text x="31" y="38" font-size="20" font-weight="800" text-anchor="middle" fill="{col}">&lt;/&gt;</text>',
        "robot": f'<rect x="12" y="18" width="40" height="32" rx="9" fill="{col}"/><circle cx="24" cy="33" r="4.5" fill="#fff"/><circle cx="40" cy="33" r="4.5" fill="#fff"/><line x1="32" y1="18" x2="32" y2="9" stroke="{col}" stroke-width="3"/><circle cx="32" cy="8" r="3.5" fill="{col}"/><rect x="25" y="41" width="14" height="3" rx="1.5" fill="#fff"/>',
        "shield": f'<path d="M32 6l20 7v15c0 13-8.5 22-20 28-11.5-6-20-15-20-28V13z" fill="{col}22" stroke="{col}" stroke-width="2.8"/><path d="M23 31l7 7 12-13" stroke="{col}" stroke-width="3.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        "nebula": f'<circle cx="32" cy="32" r="22" fill="{col}22"/><circle cx="32" cy="32" r="12" fill="{col}55"/><circle cx="14" cy="18" r="3.5" fill="{col}"/><circle cx="50" cy="20" r="3" fill="{col}"/><circle cx="47" cy="50" r="4" fill="{col}"/><line x1="14" y1="18" x2="27" y2="28" stroke="{col}" stroke-width="2"/><line x1="50" y1="20" x2="38" y2="28" stroke="{col}" stroke-width="2"/><line x1="47" y1="50" x2="37" y2="38" stroke="{col}" stroke-width="2"/>',
        "compare": f'<rect x="6" y="12" width="22" height="30" rx="3" fill="#fff" stroke="{col}" stroke-width="2.5"/><rect x="36" y="22" width="22" height="30" rx="3" fill="#fff" stroke="{col}" stroke-width="2.5"/><path d="M28 24h7M32 20l4 4-4 4M36 44h-7M32 40l-4 4 4 4" stroke="{col}" stroke-width="2.5" fill="none" stroke-linecap="round"/>',
        "rules": f'<rect x="10" y="8" width="44" height="48" rx="6" fill="#fff" stroke="{col}" stroke-width="2.6"/><path d="M18 22l4 4 7-8M18 36l4 4 7-8" stroke="{col}" stroke-width="2.8" fill="none" stroke-linecap="round"/><line x1="34" y1="22" x2="46" y2="22" stroke="{col}" stroke-width="2.6"/><line x1="34" y1="36" x2="46" y2="36" stroke="{col}" stroke-width="2.6"/><line x1="18" y1="48" x2="46" y2="48" stroke="{col}" stroke-width="2.6" stroke-dasharray="4 3"/>',
        "stars": f'<circle cx="14" cy="44" r="5" fill="{col}"/><circle cx="32" cy="18" r="6.5" fill="{col}"/><circle cx="51" cy="40" r="4.5" fill="{col}"/><line x1="14" y1="44" x2="32" y2="18" stroke="{col}" stroke-width="2.4"/><line x1="32" y1="18" x2="51" y2="40" stroke="{col}" stroke-width="2.4" stroke-dasharray="4 3"/><text x="32" y="60" font-size="11" font-weight="800" text-anchor="middle" fill="{col}">{{ }}</text>',
        "user": f'<circle cx="32" cy="20" r="11" fill="{col}"/><path d="M12 56c0-12 9-19 20-19s20 7 20 19z" fill="{col}"/>',
        "window": f'<rect x="6" y="10" width="52" height="42" rx="6" fill="#fff" stroke="{col}" stroke-width="2.8"/><line x1="6" y1="20" x2="58" y2="20" stroke="{col}" stroke-width="2.6"/><circle cx="12" cy="15" r="1.8" fill="{col}"/><circle cx="18" cy="15" r="1.8" fill="{col}"/><circle cx="18" cy="32" r="4" fill="{col}55"/><line x1="26" y1="30" x2="50" y2="30" stroke="{col}" stroke-width="2.5"/><line x1="26" y1="40" x2="44" y2="40" stroke="{col}" stroke-width="2.5"/>',
        "gear": f'<circle cx="32" cy="32" r="10" fill="none" stroke="{col}" stroke-width="5"/><g stroke="{col}" stroke-width="6" stroke-linecap="round"><line x1="32" y1="6" x2="32" y2="13"/><line x1="32" y1="51" x2="32" y2="58"/><line x1="6" y1="32" x2="13" y2="32"/><line x1="51" y1="32" x2="58" y2="32"/><line x1="13.6" y1="13.6" x2="18.5" y2="18.5"/><line x1="45.5" y1="45.5" x2="50.4" y2="50.4"/><line x1="13.6" y1="50.4" x2="18.5" y2="45.5"/><line x1="45.5" y1="18.5" x2="50.4" y2="13.6"/></g>',
        "flow": f'<rect x="24" y="6" width="16" height="12" rx="2" fill="{col}55" stroke="{col}" stroke-width="2.2"/><rect x="6" y="44" width="14" height="12" rx="2" fill="{col}55" stroke="{col}" stroke-width="2.2"/><rect x="25" y="44" width="14" height="12" rx="2" fill="{col}55" stroke="{col}" stroke-width="2.2"/><rect x="44" y="44" width="14" height="12" rx="2" fill="{col}55" stroke="{col}" stroke-width="2.2"/><path d="M32 18v13M13 44V31h38v13M32 31v13" stroke="{col}" stroke-width="2.2" fill="none"/>',
        "log": f'<rect x="10" y="6" width="44" height="52" rx="6" fill="#fff" stroke="{col}" stroke-width="2.6"/><g stroke="{col}" stroke-width="2.6"><line x1="18" y1="18" x2="46" y2="18"/><line x1="18" y1="28" x2="46" y2="28"/><line x1="18" y1="38" x2="38" y2="38"/></g><circle cx="44" cy="46" r="9" fill="{col}"/><path d="M44 41v5l3.5 2.5" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round"/>',
        "chart": f'<line x1="8" y1="54" x2="58" y2="54" stroke="{col}" stroke-width="2.8"/><rect x="13" y="34" width="9" height="20" rx="2" fill="{col}88"/><rect x="28" y="22" width="9" height="32" rx="2" fill="{col}"/><rect x="43" y="12" width="9" height="42" rx="2" fill="{col}bb"/>',
        "pencil": f'<path d="M12 50l4-13 26-26 9 9-26 26z" fill="{col}33" stroke="{col}" stroke-width="2.8" stroke-linejoin="round"/><line x1="36" y1="17" x2="45" y2="26" stroke="{col}" stroke-width="2.8"/><line x1="10" y1="56" x2="54" y2="56" stroke="{col}" stroke-width="2.8"/>',
        "loop": f'<path d="M50 30a18 18 0 1 0-4 14" fill="none" stroke="{col}" stroke-width="4" stroke-linecap="round"/><path d="M52 18v13H39" fill="none" stroke="{col}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>',
        "db": f'<ellipse cx="32" cy="14" rx="20" ry="7" fill="{col}33" stroke="{col}" stroke-width="2.6"/><path d="M12 14v34c0 4 9 7 20 7s20-3 20-7V14M12 31c0 4 9 7 20 7s20-3 20-7" fill="none" stroke="{col}" stroke-width="2.6"/>',
        "cloud": f'<path d="M18 46h30a11 11 0 0 0 0-22 15 15 0 0 0-28-3A12 12 0 0 0 18 46z" fill="{col}22" stroke="{col}" stroke-width="2.6"/><text x="33" y="40" font-size="10" font-weight="800" text-anchor="middle" fill="{col}">API</text>',
        "train": f'<rect x="10" y="10" width="44" height="36" rx="8" fill="{col}22" stroke="{col}" stroke-width="2.6"/><rect x="17" y="17" width="30" height="13" rx="3" fill="{col}55"/><circle cx="20" cy="38" r="3" fill="{col}"/><circle cx="44" cy="38" r="3" fill="{col}"/><path d="M18 46l-6 10M46 46l6 10" stroke="{col}" stroke-width="2.6"/>',
        "coin": f'<circle cx="32" cy="32" r="22" fill="{col}22" stroke="{col}" stroke-width="2.8"/><text x="32" y="41" font-size="24" font-weight="800" text-anchor="middle" fill="{col}">$</text>',
    }[name]
    return f'<svg width="{s}" height="{s}" viewBox="0 0 64 64">{p}</svg>'


def card(x, y, w, h, color, inner, dashed=False):
    dark, bg, border = C[color]
    style = "dashed" if dashed else "solid"
    return f'<div class="c" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{bg};border-color:{border};border-style:{style}">{inner}</div>'


def step(n, color, title, en, ic, desc, ex=""):
    dark = C[color][0]
    return (f'<div class="head"><span class="num" style="background:{dark}">{n}</span><div><div class="t" style="color:{dark}">{title}</div>'
            f'<div class="en" style="color:{dark}">{en}</div></div></div>'
            f'<div style="text-align:center;margin:12px 0 8px">{icon(ic, dark, 70)}</div>'
            f'<div class="d" style="text-align:center">{desc}</div>' + (f'<div class="ex" style="text-align:center;margin-top:6px">{ex}</div>' if ex else ""))


def arrows(w, h, paths):
    defs = (f'<defs><marker id="a" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="4.6" markerHeight="4.6" orient="auto">'
            f'<path d="M0 0L10 5L0 10z" fill="{NAVY}"/></marker></defs>')
    norm = [(p if isinstance(p, tuple) else (p, 3, False)) for p in paths]
    dash_attr = ' stroke-dasharray="6 5"'
    body = "".join(f'<path d="{d}" fill="none" stroke="{NAVY}" stroke-width="{sw}" marker-end="url(#a)" stroke-linejoin="round"{dash_attr if dash else ""}/>'
                   for d, sw, dash in norm)
    return f'<svg class="ar" width="{w}" height="{h}">{defs}{body}</svg>'


def page(name, w, h, body):
    html = f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div style="position:relative;width:{w}px;height:{h}px">{body}</div></body></html>'
    f = OUT / f"{name}.html"
    f.write_text(html, encoding="utf-8")
    png = OUT / f"{name}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--window-size={w},{h}", f"--screenshot={png}", f"file://{f}"], capture_output=True)
    print(png, png.exists())


# ---------------------------------------------------------------- 1. 서비스 흐름
def d1():
    W, H = 1440, 790
    b = '<h1 style="top:22px">나의 우주 — 글 한 편이 별이 되기까지</h1><div class="sub" style="top:78px">Service Workflow · 글을 올리면 두 Studio 에이전트와 코드가 차례로 일한다</div>'
    cw, ch, gx = 300, 262, 46
    xs = [40 + i * (cw + gx) for i in range(4)]
    y1, y2 = 140, 482
    row1 = [("blue", "대화 · 글 · 사진", "Talk · Write · Photo", "doc_up", "대화로 쓰기(요약 확인 후),<br>텍스트, 손글씨 사진", "MVP: 직접 쓰기 · MD·TXT · 인스타 ZIP"),
            ("green", "공통 기록 → HTML", "Common Record", "doc_code", "출처와 무관한 기록으로 바꾸고<br>HTML로 Studio에 보냄", "이어진 게시물 묶기 · 제목 날짜 · 소제목"),
            ("purple", "기록 Agent", "Studio · Parse → Classify → Extract", "robot", "글 유형을 고르고<br>생각을 하나씩 나눔", "주제 · 종류 · 확신 · 원문 인용 · 가치"),
            ("orange", "관문", "Gates G1 · G2 · G4", "shield", "원문에 없는 인용은 버리고<br>날짜 확인, 실명은 ○○", "결과를 내보내기 전에 매번")]
    row2 = [("teal", "성운 연결 · 과거 고르기", "Embedding", "nebula", "주제를 성운에 붙이고<br>관련 과거 생각 최대 10개", "같은 성운이거나 비슷한 생각"),
            ("yellow", "관측 Agent", "Studio · Parse → Classify → Extract", "compare", "오늘 생각(T)과 과거 생각(P)을<br>비교해 관계를 판정", "관측 상태 6가지 중 하나"),
            ("pink", "관계 규칙", "Rules + Gate G3", "rules", "시간 · 감정 규칙으로 거르고<br>실선/점선을 정함", "감정이 달라진 것은 바뀜이 아님"),
            ("blue", "보고서 · 한마디 · 우주", "Report · Words · Universe", "stars", "근거 인용이 붙은 보고서,<br>위로·격려 한마디, 새 별", "정리된 기록 파일로 저장")]
    for i, r in enumerate(row1):
        b += card(xs[i], y1, cw, ch, r[0], step(i + 1, *r))
    for i, r in enumerate(row2):
        b += card(xs[i], y2, cw, ch, r[0], step(i + 5, *r))
    paths = [f"M{xs[i] + cw + 6},{y1 + ch / 2} L{xs[i + 1] - 8},{y1 + ch / 2}" for i in range(3)]
    paths += [f"M{xs[i] + cw + 6},{y2 + ch / 2} L{xs[i + 1] - 8},{y2 + ch / 2}" for i in range(3)]
    paths.append(f"M{xs[3] + cw + 6},{y1 + ch / 2} H{W - 14} V{(y1 + ch + y2) / 2} H{16} V{y2 + ch / 2} H{xs[0] - 8}")
    b += arrows(W, H, paths)
    page("my-universe-1-workflow", W, H, b)


# ---------------------------------------------------------------- 2. 전체 구조
def d2():
    W, H = 1440, 1030
    b = '<h1 style="top:22px">Overall Architecture</h1><div class="sub" style="top:78px">나의 우주 전체 구조 (MVP)</div>'
    layers = [("blue", "Presentation", 150, 104), ("green", "Service", 278, 104), ("yellow", "Application<br>(Python 코드)", 406, 150),
              ("purple", "Agent", 590, 140), ("teal", "Result", 766, 104), ("gray", "Infrastructure", 900, 104)]
    for col, name, y, h in layers:
        dark, bg, br = C[col]
        b += f'<div class="c" style="left:30px;top:{y}px;width:200px;height:{h}px;background:{bg};border-color:{br};display:flex;align-items:center;justify-content:center;text-align:center;font-weight:800;font-size:19px;color:{dark}">{name}<br>Layer</div>'

    def row(x, y, w, h, color, ic, title, desc, dashed=False):
        dark = C[color][0]
        return card(x, y, w, h, color, f'<div style="display:flex;align-items:center;gap:16px;height:100%">{icon(ic, dark, 58)}'
                                       f'<div><div class="t" style="font-size:20px">{title}</div><div class="d">{desc}</div></div></div>', dashed)
    X, Wd = 270, 1130
    b += row(X, 150, Wd, 104, "blue", "window", "화면", "💬 대화 일기(목업 · 2차) &nbsp;|&nbsp; 🌌 우주 · 관측 보고서 &nbsp;|&nbsp; ✍️ 글쓰기 &nbsp;|&nbsp; 📥 가져오기 &nbsp;|&nbsp; 🛠 운영(Ops) — Streamlit")
    b += row(X, 278, Wd, 104, "green", "gear", "service.py — 글 한 편 → 관측 보고서", "두 에이전트와 코드를 순서대로 부르고 보고서를 조립 · 세션당 실행 한도로 크레딧 보호")
    mods = [("importer", "공통 기록 · HTML 변환"), ("gates", "관문 G1 · G2 · G3 · G4"), ("universe", "성운 · 과거 고르기 · 관계 규칙 · 별 자리"), ("observe_builder", "비교 입력 HTML (T1… P1…)")]
    mw = (Wd - 3 * 16) / 4
    for i, (m, d) in enumerate(mods):
        b += card(X + i * (mw + 16), 406, mw, 150, "yellow", f'<div style="text-align:center">{icon("flow", C["yellow"][0], 46)}<div class="t" style="font-size:18px;margin-top:4px">{m}.py</div><div class="ex" style="font-size:14px">{d}</div></div>')
    b += f'<div class="c" style="left:{X - 14}px;top:580px;width:{Wd + 28}px;height:160px;border-color:{C["purple"][2]};border-style:dashed;background:transparent"></div>'
    aw = (Wd - 2 * 20) / 3
    for i, (t, d, col) in enumerate([("기록 Agent", "Studio · 글 유형 4갈래 → 생각 나누기", "purple"), ("관측 Agent", "Studio · 관측 상태 6갈래 → 관계 판정", "purple"), ("Solar Embedding", "같은 이야기인가 (주제 → 성운)", "teal")]):
        b += row(X + i * (aw + 20), 594, aw, 132, col, "robot" if i < 2 else "nebula", t, d)
    rw = (Wd - 2 * 20) / 3
    for i, (t, d, ic) in enumerate([("관측 보고서 JSON", "근거 인용 · 관측 상태 · 질문", "stars"), ("정리된 기록 파일", "우주 전체 (JSON, 사용자가 보관)", "db"), ("실행 기록", "시간 · 비용 · 관문 (원문 없음)", "log")]):
        b += row(X + i * (rw + 20), 766, rw, 104, "teal", ic, t, d)
    infra = [("cloud", "Files API", "HTML 업로드"), ("cloud", "Agents (Jobs) API", "에이전트 실행"), ("cloud", "Embeddings API", "solar-embedding-2"),
             ("db", "저장", "서버 저장 없음"), ("train", "배포", "Railway")]
    iw = (Wd - 4 * 12) / 5
    b += f'<div class="c" style="left:{X - 14}px;top:900px;width:{Wd + 28}px;height:104px;border-color:{C["gray"][2]};border-style:dashed;background:#fbfbfc"></div>'
    for i, (ic, t, d) in enumerate(infra):
        b += f'<div style="position:absolute;left:{X + i * (iw + 12)}px;top:925px;width:{iw}px;display:flex;align-items:center;gap:10px">{icon(ic, C["gray"][0], 50)}<div><div style="font-weight:800;font-size:16px">{t}</div><div class="ex">{d}</div></div></div>'
    cx = X + Wd / 2
    paths = [f"M{cx},256 L{cx},274", f"M{cx},384 L{cx},402", f"M{cx},558 L{cx},590", f"M{cx},742 L{cx},762"]
    b += arrows(W, H, paths)
    page("my-universe-2-architecture", W, H, b)


# ---------------------------------------------------------------- 3. 에이전트 동작
def d3():
    W, H = 1440, 1170
    b = '<h1 style="top:22px">두 에이전트는 이렇게 일한다</h1><div class="sub" style="top:78px">HR 예시의 Resume·JD Agent → matching_builder → Matching Agent와 같은 구조</div>'

    def node(x, y, w, h, color, title, en, body):
        dark = C[color][0]
        return card(x, y, w, h, color, f'<div class="t" style="font-size:19px;color:{dark}">{title}</div><div class="en" style="color:{dark}">{en}</div><div style="margin-top:8px">{body}</div>')

    def chips(items, color):
        dark, _, br = C[color]
        return "".join(f'<span class="chip" style="border-color:{br};color:{dark}">{i}</span>' for i in items)

    def agent(y, title, sub, parse_d, cls_items, cls_note, ext_items, ext_note):
        dark, bg, br = C["purple"]
        s = (f'<div class="c" style="left:40px;top:{y}px;width:1360px;height:300px;border-color:{br};background:{bg}">'
             f'<div class="head">{icon("robot", dark, 44)}<div style="margin-left:12px"><div class="t" style="color:{dark}">{title}</div><div class="en" style="color:{dark}">{sub}</div></div></div></div>')
        s += node(70, y + 84, 300, 196, "blue", "① Parse", "Document Parse", f'<div class="d">{parse_d}</div>')
        s += node(420, y + 84, 430, 196, "orange", "② Classify", "갈래 나누기", chips(cls_items, "orange") + f'<div class="ex" style="margin-top:8px">{cls_note}</div>')
        s += node(900, y + 84, 470, 196, "pink", "③ Extract", "갈래마다 같은 스키마", chips(ext_items, "pink") + f'<div class="ex" style="margin-top:8px">{ext_note}</div>')
        return s, [f"M372,{y + 182} L414,{y + 182}", f"M852,{y + 182} L894,{y + 182}"]

    a1, p1 = agent(130, "기록 Agent", "Studio · classify-extract · 글 한 편 → 구조화 JSON", "HTML로 보낸 글을<br>읽을 수 있는 텍스트로",
                   ["경험 기록", "생각·성찰", "창작", "기타"], "신앙 묵상 · 기도도 생각·성찰 (종교 유형 없음)",
                   ["summary", "period", "triggers", "addressee", "roles(실명 X)", "references", "events", "thoughts[ ]"],
                   "thoughts = topic · thought · kind(해석·신념·질문·다짐·반성·감정) · certainty · quote(원문 그대로) · self_change · value(10개 중)")
    b += a1
    # 코드 조립
    dark, bg, br = C["yellow"]
    b += f'<div class="c" style="left:40px;top:468px;width:1360px;height:212px;border-color:{br};background:{bg}"><div class="head">{icon("flow", dark, 44)}<div style="margin-left:12px"><div class="t" style="color:{dark}">코드 (Python) — 두 에이전트 사이</div><div class="en" style="color:{dark}">matching_builder에 해당하는 부분</div></div></div></div>'
    steps = [("orange", "관문 G1 · G2 · G4", "인용이 원문에 없으면 버림<br>날짜 확인 · 실명은 ○○"), ("teal", "주제 → 성운", "임베딩 (중심 보정)<br>비슷하면 붙이고 아니면 새 성운"),
             ("teal", "과거 생각 고르기", "같은 성운이거나<br>비슷한 생각, 최대 10개"), ("yellow", "비교 입력 HTML", "오늘 생각 T1, T2 …<br>과거 생각 P1, P2 …")]
    sw = 300
    for i, (col, t, d) in enumerate(steps):
        b += node(70 + i * (sw + 28), 544, sw, 120, col, t, "", f'<div class="ex" style="font-size:14px">{d}</div>')
    p_code = [f"M{70 + i * (sw + 28) + sw + 4},604 L{70 + (i + 1) * (sw + 28) - 6},604" for i in range(3)]
    a2, p2 = agent(714, "관측 Agent", "Studio · classify-extract · 비교 입력 → 관측 보고서", "T(오늘) · P(과거) 목록을<br>텍스트로",
                   ["해소", "바뀜", "긴장", "어긋남", "이어짐", "처음 쓰는 주제"], "겹치면 해소 > 바뀜 > 긴장 > 어긋남 > 이어짐 > 처음",
                   ["state", "summary", "question", "relations[ ]"],
                   "relations = type · today_id · past_id · topic · explanation · author_stated · axis<br>감정이 달라진 것만으로는 바뀜이 아님")
    b += a2
    # 결과
    b += node(40, 1046, 1360, 96, "green", "→ 코드: 관계 규칙 + 관문 G3 → 관측 보고서 JSON · 우주 별자리", "",
              '<div class="ex" style="font-size:14.5px">없는 ID 버림 · 바뀜은 7일 이상 · 긴장은 30일 이내 · 목표 충돌은 14일 이내 · 감정끼리 바뀜 버림 · 작성자가 직접 쓴 변화·정리만 실선 · 사람 단정 표현은 바꿈</div>')
    paths = p1 + p_code + p2 + ["M720,432 L720,464", "M720,682 L720,710", "M720,1016 L720,1042"]
    b += arrows(W, H, paths)
    page("my-universe-3-agents", W, H, b)


# ---------------------------------------------------------------- 4. Ops 루프
def d4():
    W, H = 1440, 1110
    b = '<h1 style="top:22px">Ops — 나의 우주를 운영하는 방법</h1><div class="sub" style="top:78px">같은 평가 세트로 재고, 고치고, 다시 재서 나아졌을 때만 올린다</div>'
    cw, ch = 380, 250
    xs = [40, 530, 1020]
    yt, yb = 150, 560
    top = [("blue", "실행", "Run · config 고정", "robot", "Studio 에이전트를<br>정해 둔 설정 번호로 실행", "기록 Agent config #1 · 관측 Agent config #1"),
           ("green", "실행 기록", "Run Log (원문 없음)", "log", "실행마다 시간 · 비용 · 관문 결과<br>· 개수만 남김", "예: run_0412 · 기록 #1 · 생각 5 · 41초 · $0.10"),
           ("orange", "실시간 관문", "Gates", "shield", "원문에 없는 인용, 실명, 단정 표현을<br>화면에 내보내기 전에 거름", "걸린 비율이 갑자기 오르면 경고 신호")]
    bottom = [("purple", "회귀 검사 · 올리기", "Regression · Promote", "loop", "관문 0건 유지 + 지표가 나아졌을 때만<br>.env의 CONFIG_ID를 새 번호로", "나빠지면 이전 번호로 되돌리기"),
              ("pink", "고치기", "Fix in Studio", "pencil", "Studio의 설명(프롬프트)을 고치면<br>새 설정 번호가 생김", "예: \"반성 = 기준에 비춰 나를 평가함\" 추가 → #2"),
              ("teal", "측정", "Measure", "chart", "설계한 관계 찾기 · 흔들림 ·<br>비용 · 지연 · 생각 종류 정확도", "예: 같은 글 3번 → 생각 수가 같은가")]
    for i, r in enumerate(top):
        b += card(xs[i], yt, cw, ch, r[0], step(i + 1, *r))
    for i, r in enumerate(bottom):
        b += card(xs[i], yb, cw, ch, r[0], step(6 - i, *r))
    # 가운데 평가 세트
    dark, bg, br = C["yellow"]
    b += card(470, 420, 500, 116, "yellow", f'<div style="display:flex;gap:14px;align-items:center">{icon("db", dark, 52)}<div><div class="t" style="font-size:19px;color:{dark}">고정 평가 세트</div><div class="ex" style="font-size:14px">가상 글 29편 + 심어 둔 관계 8개 · 금지 관계 1개<br>(1차 최종) 팀원 둘이 붙인 생각 종류 정답</div></div></div>')
    paths = [f"M{xs[0] + cw + 6},{yt + ch / 2} L{xs[1] - 8},{yt + ch / 2}", f"M{xs[1] + cw + 6},{yt + ch / 2} L{xs[2] - 8},{yt + ch / 2}",
             f"M{xs[2] + cw / 2},{yt + ch + 6} L{xs[2] + cw / 2},{yb - 8}",
             f"M{xs[2] - 6},{yb + ch / 2} L{xs[1] + cw + 8},{yb + ch / 2}", f"M{xs[1] - 6},{yb + ch / 2} L{xs[0] + cw + 8},{yb + ch / 2}",
             f"M{xs[0] + cw / 2},{yb - 6} L{xs[0] + cw / 2},{yt + ch + 8}"]
    b += arrows(W, H, paths)
    # 아래 패널 두 개
    gd, gb, gbr = C["gray"]
    b += card(40, 860, 660, 226, "gray", f'<div class="head">{icon("coin", gd, 44)}<div class="t" style="margin-left:12px;color:{gd}">비용 지키기</div></div>'
              '<div class="d" style="margin-top:12px;line-height:1.75">· 이미 우주에 있는 글은 다시 보내지 않음<br>· 세션당 Studio 실행 40회 · 가져오기 한 번에 10편<br>'
              '· 가져오기 전에 예상 시간 · 비용을 먼저 보여 줌<br>· 실패하면 한 번 다시 시도, 멈춘 글부터 이어서<br>· 디스크 캐시는 로컬 개발에서만 (서버에 글을 남기지 않음)</div>')
    tag = lambda t, c: f'<span class="tag" style="background:{C[c][1]};color:{C[c][0]};border:1px solid {C[c][2]}">{t}</span>'
    b += card(740, 860, 660, 226, "gray", f'<div class="head">{icon("loop", gd, 44)}<div class="t" style="margin-left:12px;color:{gd}">언제 무엇을</div></div>'
              f'<div class="d" style="margin-top:12px;line-height:1.75">{tag("오늘 MVP", "blue")} 실행 기록 · 실시간 관문 · 흔들림 측정 · 캐시<br>'
              f'{tag("1차 최종", "purple")} 생각 종류 정확도 루프(E7): 팀원 둘의 정답 → config #1 → #2<br>'
              f'{tag("1차 최종", "purple")} 사용자의 "맞다/아니다" = 운영 중 평가 (점선 승인률)<br>'
              f'{tag("2차", "teal")} 버전이 섞인 우주 다시 돌리기 · 분류 목록 드리프트<br>{tag("2차", "teal")} GitHub Actions로 회귀 검사 자동화</div>')
    page("my-universe-4-ops", W, H, b)

# ---------------------------------------------------------------- 5. Ops가 붙는 자리
def d5():
    W, H = 1600, 1040
    b = ('<h1 style="top:20px">Ops는 어디에서 일어나나</h1>'
         '<div class="sub" style="top:76px">위: 글 한 편이 지나가는 서비스 길과 Ops가 붙는 자리(A~H) · 아래: 설정을 바꿀 때 도는 품질 루프</div>')
    lane = lambda y, t, c: f'<div style="position:absolute;left:40px;top:{y}px;font-size:19px;font-weight:800;color:{C[c][0]}">{t}</div>'
    b += lane(126, "① 서비스 길 — 글 한 편이 들어올 때마다 (온라인)", "blue")

    cw, ch, y0 = 170, 128, 196
    gap = (W - 80 - 8 * cw) / 7
    xs = [40 + i * (cw + gap) for i in range(8)]
    nodes = [("blue", "doc_up", "대화 · 글 · 사진", "MVP: 직접 · MD · TXT · ZIP"), ("green", "doc_code", "공통 기록", "출처와 무관 → HTML"),
             ("purple", "robot", "기록 Agent", "Studio · 생각 나누기"), ("orange", "shield", "관문", "G1 · G2 · G4"),
             ("teal", "nebula", "성운 · 과거", "임베딩 · 과거 생각 10개"), ("purple", "robot", "관측 Agent", "Studio · 관계 판정"),
             ("pink", "rules", "관계 규칙", "시간 · 감정 규칙 · G3"), ("blue", "stars", "보고서 · 우주", "JSON · 별자리")]
    for x, (col, ic, t, d) in zip(xs, nodes):
        dark = C[col][0]
        bw = "3px" if t.endswith("Agent") else "2px"
        b += card(x, y0, cw, ch, col, f'<div style="text-align:center">{icon(ic, dark, 46)}<div class="t" style="font-size:17px;color:{dark};margin-top:2px">{t}</div>'
                                      f'<div class="ex" style="font-size:12.5px">{d}</div></div>').replace("border:2px solid", f"border:{bw} solid")
    for x in (xs[2], xs[5]):   # B 설정 버전 꼬리표
        b += (f'<div style="position:absolute;left:{x + cw / 2 - 58}px;top:{y0 - 16}px;width:116px;height:28px;border-radius:999px;background:{C["purple"][0]};'
              f'color:#fff;font-weight:800;font-size:13.5px;display:flex;align-items:center;justify-content:center">B · config #1</div>')
    paths = [f"M{xs[i] + cw + 3},{y0 + ch / 2} L{xs[i + 1] - 5},{y0 + ch / 2}" for i in range(7)]

    def badge(letter, now):
        g = C["green"][0]
        return (f'<span style="display:inline-flex;flex:none;width:24px;height:24px;border-radius:50%;align-items:center;justify-content:center;'
                f'font-weight:800;font-size:13px;margin-right:7px;{"background:" + g + ";color:#fff" if now else "border:2px solid #9aa3b5;color:#5b6478"}">{letter}</span>')

    def callout(x, y, items):
        rows = "".join(f'<div style="display:flex;align-items:flex-start;margin:0 0 9px">{badge(l, now)}<div><div style="font-weight:800;font-size:13.5px">{t}</div>'
                       f'<div class="ex" style="font-size:12px">{d}</div></div></div>' for l, now, t, d in items)
        return f'<div style="position:absolute;left:{x - 10}px;top:{y}px;width:{cw + 20}px;background:#fff;border:1.5px solid #dfe3ea;border-radius:12px;padding:10px 10px 2px">{rows}</div>'

    yc = y0 + ch + 34
    agent_ops = [("A", True, "비용 지키기", "같은 글은 다시 안 보냄 · 세션 40회 상한"), ("C", True, "재시도", "실패하면 한 번 더"),
                 ("D", True, "실행 기록", "시간 · 비용 · 쪽수 (원문 없음)")]
    b += callout(xs[2], yc, agent_ops + [("F", True, "흔들림 측정", "같은 글 3번 → 결과가 같은가")])
    b += callout(xs[3], yc, [("E", True, "관문", "걸린 생각은 화면에 안 올림 · 걸린 수 기록")])
    b += callout(xs[4], yc, [("H", False, "드리프트 지표", "성운 수 · '기타' 비율이 갑자기 변하나")])
    b += callout(xs[5], yc, agent_ops + [("F", False, "흔들림 측정", "관측 Agent도 같은 글 3번")])
    b += callout(xs[6], yc, [("E", True, "관문 G3", "사람을 단정하는 문장은 바꿈")])
    b += callout(xs[7], yc, [("G", False, "사용자 확인", "점선 '맞다/아니다' = 운영 중 평가")])
    dash = lambda x: f'<div style="position:absolute;left:{x + cw / 2}px;top:{y0 + ch}px;height:{yc - y0 - ch}px;border-left:2px dashed #b8c0cf"></div>'
    b += "".join(dash(xs[i]) for i in (2, 3, 4, 5, 6, 7))

    # ② 품질 루프
    yl = 690
    b += lane(yl - 44, "② 품질 루프 — Studio 설명(설정)을 바꿀 때마다 (오프라인 평가 · 회귀)", "purple")
    bw4, bh = 340, 150
    g4 = (W - 80 - 4 * bw4) / 3
    bx = [40 + i * (bw4 + g4) for i in range(4)]
    loop = [("yellow", "db", "고정 평가 세트", "가상 글 29편 + 심어 둔 관계 8개 + 금지 관계 1개<br>(다음) 팀원 둘이 붙인 생각 종류 정답"),
            ("purple", "robot", "같은 길로 돌리기", "위 서비스 길을 그대로 (python app.py)<br>config #1과 #2를 같은 글로"),
            ("teal", "chart", "비교", "관계 종류 맞힘 · 실선/점선 일치<br>금지 관계 · 관문 걸림 · 비용 · 시간"),
            ("pink", "loop", "올리기 / 되돌리기", "나아졌으면 .env의 CONFIG_ID = 2<br>나빠지면 1로 그대로")]
    for i, (x, (col, ic, t, d)) in enumerate(zip(bx, loop)):
        dark = C[col][0]
        b += card(x, yl, bw4, bh, col, f'<div class="head"><span class="num" style="background:{dark}">{i + 1}</span><div class="t" style="font-size:19px;color:{dark}">{t}</div>'
                                         f'<div style="margin-left:auto">{icon(ic, dark, 40)}</div></div><div class="d" style="font-size:14px;margin-top:10px">{d}</div>')
    paths += [f"M{bx[i] + bw4 + 4},{yl + bh / 2} L{bx[i + 1] - 6},{yl + bh / 2}" for i in range(3)]
    b += arrows(W, H, paths)
    # 올리기 → 두 에이전트의 config 꼬리표 (보라 점선)
    pc = C["purple"][0]
    cx3, cx6, top = xs[2] + cw / 2, xs[5] + cw / 2, y0 - 34
    b += (f'<svg class="ar" width="{W}" height="{H}"><defs><marker id="p" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="4.6" markerHeight="4.6" orient="auto">'
          f'<path d="M0 0L10 5L0 10z" fill="{pc}"/></marker></defs>'
          f'<path d="M{bx[3] + bw4 / 2},{yl - 2} V{yl - 18} H{W - 14} V{top} H{cx3} V{y0 - 20}" fill="none" stroke="{pc}" stroke-width="2.5" stroke-dasharray="7 5" marker-end="url(#p)"/>'
          f'<path d="M{cx6},{top} V{y0 - 20}" fill="none" stroke="{pc}" stroke-width="2.5" stroke-dasharray="7 5" marker-end="url(#p)"/></svg>')
    b += f'<div style="position:absolute;left:{W - 380}px;top:{top - 26}px;font-size:13px;font-weight:800;color:{pc}">설정 번호만 바꾸면 두 에이전트가 새 설정으로 돈다</div>'
    # 밤사이 실제로 한 것 + 범례
    b += card(40, yl + bh + 26, W - 80, 92, "gray",
              '<div class="d" style="font-size:14.5px;line-height:1.6"><b>밤사이 실제로 3번 돌린 결과 (코드 규칙을 고침):</b> 관계 종류 맞힘 6/8 → 7/8 · 관계 49개 → 39개 · 근거 없는 실선 2개 → 점선 · 금지 관계 0건 유지 · 다시 돌린 비용 $0.10 (A 캐시 덕분)<br>'
              '<b>다음:</b> Studio 관측 Agent 설명을 고쳐 config #2를 만들고 같은 루프로 비교 → 거짓 별자리(설계 밖 관계의 약 1/3)를 줄이는 것이 목표</div>')
    b += (f'<div style="position:absolute;left:40px;top:{H - 44}px;font-size:13.5px;color:#5b6478;display:flex;align-items:center">'
          f'{badge("A", True)}오늘 MVP에 들어 있음 &nbsp;&nbsp;&nbsp; {badge("G", False)}다음 단계 &nbsp;&nbsp;&nbsp;'
          f'<span style="display:inline-block;width:26px;border-top:2px dashed #b8c0cf;margin:0 7px 0 4px"></span>그 단계에 붙는 Ops</div>')
    page("my-universe-5-ops-map", W, H, b)

# ---------------------------------------------------------------- 6. 온톨로지 표
def d6():
    W, H = 1600, 1060
    b = ('<h1 style="top:20px">나의 우주 온톨로지 — 미리 정해 둔 표</h1>'
         '<div class="sub" style="top:76px">무엇을(대상) · 어떤 칸으로(속성) · 어떤 값만(정해진 값) 기록하는가</div>')

    def chips(items, color, open_=False):
        dark, _, br = C[color]
        st = "dashed" if open_ else "solid"
        return "".join(f'<span class="chip" style="border-color:{br};border-style:{st};color:{dark};font-size:13px;padding:2px 9px">{i}</span>' for i in items)

    def cls(x, y, w, h, color, ic, title, en, rows):
        dark = C[color][0]
        body = "".join(f'<div style="margin-top:9px"><div style="font-size:13px;font-weight:800;color:#33415c">{k}</div><div>{v}</div></div>' for k, v in rows)
        return card(x, y, w, h, color, f'<div class="head">{icon(ic, dark, 38)}<div style="margin-left:10px"><div class="t" style="font-size:20px;color:{dark}">{title}</div>'
                                       f'<div class="en" style="color:{dark}">{en}</div></div></div>{body}')

    b += cls(40, 130, 470, 300, "blue", "doc_up", "기록", "Record · 글 한 편 (대화 · 텍스트 · 사진)", [
        ("글 유형", chips(["경험 기록", "생각·성찰", "창작", "기타"], "blue")),
        ("출처 · 날짜", chips(["대화", "텍스트", "사진", "인스타"], "blue") + chips(["다루는 날: 확실 / 추정"], "gray")),
        ("확인 (대화로 쓴 글만)", chips(["확인 전", "확인됨"], "blue")),
    ])
    b += cls(40, 460, 470, 220, "green", "doc_code", "부분", "Section · 소제목 단위", [
        ("계기", chips(["경험", "대화", "읽은 글", "콘텐츠", "뉴스·사건"], "green")),
        ("말 거는 대상", chips(["나", "독자", "특정 인물", "신"], "green")),
    ])
    b += cls(40, 710, 470, 160, "gray", "user", "사람", "Person · 실명은 저장하지 않음", [
        ("역할만", chips(["선배", "친구", "가족", "팀원", "리더", "…"], "gray", True)),
    ])
    b += cls(565, 130, 500, 420, "purple", "robot", "생각", "Thought · 별자리의 단위", [
        ("종류", chips(["해석", "신념·원칙", "질문", "다짐", "반성", "감정"], "purple")),
        ("확신", chips(["단정", "고민 중", "질문"], "purple")),
        ("가치", chips(["자율", "도전", "즐거움", "성취", "영향력", "안정", "규범", "전통·신앙", "배려", "공익"], "purple")),
        ("근거", chips(["원문 인용 (필수 · 글자 그대로)", "스스로 쓴 변화"], "gray")),
    ])
    b += cls(565, 580, 500, 290, "pink", "rules", "관계", "Relation · 생각 ↔ 생각", [
        ("종류", chips(["이어짐", "바뀜", "긴장", "해소", "어긋남", "목표 충돌"], "pink")),
        ("선", chips(["실선 = 원문으로 확인", "점선 = AI 추정"], "pink")),
        ("긴장 축", chips(["혼자 ↔ 함께", "안정 ↔ 배움", "…"], "pink", True)),
    ])
    # 삶의 영역 (닫힌 10) + 세부 주제 (열린)
    dark, bg, br = C["teal"]
    doms = [("삶의 성취", "PWI", "진로 · 배움 · 면접"), ("관계", "PWI", "가족 · 친구"), ("공동체", "PWI", "동아리 · 교회"),
            ("건강", "PWI · WHOQOL", "걷기 · 수면 · 마음"), ("생활 수준", "PWI", "돈 · 집"), ("미래 안정", "PWI", "취업 걱정"),
            ("안전", "PWI", ""), ("영성·신앙", "PWI 선택 · WHOQOL", "말씀 묵상"), ("여가", "WHOQOL", "취미 · 여행")]
    grid = "".join(f'<div style="border:2px solid {br};background:#fff;border-radius:12px;padding:7px 10px;text-align:center">'
                   f'<div style="font-weight:800;color:{dark};font-size:15px">{d}</div>'
                   f'<div style="font-size:11px;color:{dark};opacity:.8">{src}</div>'
                   f'<div style="font-size:12px;color:#5b6478;margin-top:3px;border-top:1.5px dashed {br};padding-top:3px">{ex or "&nbsp;"}</div></div>' for d, src, ex in doms)
    b += card(1120, 130, 440, 740, "teal",
              f'<div class="head">{icon("nebula", dark, 40)}<div style="margin-left:10px"><div class="t" style="font-size:20px;color:{dark}">주제 = 2단</div>'
              f'<div class="en" style="color:{dark}">위: 삶의 영역 (닫힌 9개) · 아래: 세부 주제 (열린 목록)</div></div></div>'
              f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;margin-top:14px">{grid}</div>'
              f'<div class="d" style="font-size:13.5px;margin-top:14px;line-height:1.55"><b>근거:</b> 삶의 영역은 주관적 안녕감 지표 PWI(Personal Wellbeing Index, International Wellbeing Group — OECD 2013 측정 지침이 영역 평가에서 인용)의 7개 영역 + 선택 영역 "영성·종교", '
              f'WHO 삶의 질 척도 WHOQOL의 "여가"에서 가져왔다. 감정은 영역이 아니라 생각의 종류 "감정"으로 담는다.<br><br>'
              f'우주에서 <b>삶의 영역 = 태양계(해)</b>, <b>세부 주제 = 그 해를 도는 행성</b>. AI가 뽑은 세부 주제(점선 칸)는 가장 가까운 영역 하나에 붙고, 아직 글이 없는 영역은 "관측 안 된 영역"으로 남는다.</div>')
    # 연결선 (술어)
    paths = ["M512,280 C540,280 540,300 562,300", "M275,432 L275,456", "M512,790 C540,790 540,720 562,720", "M1067,330 C1092,330 1092,330 1116,330"]
    b += arrows(W, H, [(p, 2.5, False) for p in paths])
    lab = lambda x, y, t: f'<div style="position:absolute;left:{x}px;top:{y}px;font-size:12.5px;font-weight:800;color:#33415c;background:#fff;padding:0 4px">{t}</div>'
    b += lab(520, 262, "담는다") + lab(284, 434, "담는다") + lab(520, 742, "등장") + lab(1072, 306, "다룬다·속한다")
    b += lab(820, 556, "생각 ↔ 생각")
    b += card(40, 900, 1520, 120, "gray",
              '<div class="d" style="font-size:15px;line-height:1.7"><b>닫힌 목록</b>(실선 칸 · 객관식): 미리 정한 보기 중에서만 AI가 고른다 → 사람마다 · 글마다 같은 기준으로 비교할 수 있다.<br>'
              '<b>열린 목록</b>(점선 칸 · 주관식): 세부 주제 · 긴장 축 · 역할은 AI가 제안하고 사용자가 확인한다. '
              '<b>관문</b>: 원문에 없는 인용, 실명, 사람을 단정하는 말은 저장 전에 거른다.</div>')
    page("my-universe-6-ontology", W, H, b)


if __name__ == "__main__":
    d1(); d2(); d3(); d4(); d5(); d6()
