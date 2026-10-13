"""WS26 설치형 웹앱 · 소개 화면 파일 점검(빌드 없이). 화면에서 도는 시험은 infra/frontend/e2e-landing/ 이 한다.

- manifest: 설치 조건(이름 · 시작 주소 · standalone · 192/512 아이콘 · maskable)
- 아이콘 · 그림: 적힌 크기와 실제 PNG 크기가 같음
- 서비스 워커: 오프라인 안내 화면 하나만 캐시하고, 일기 · API 응답은 캐시에 넣지 않음(개인정보)
- 검색: sitemap 은 소개 · /privacy 만, 로그인 뒤 화면은 noindex
"""
import json
import re
import struct
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "infra" / "frontend"
PUB = WEB / "public"


def png_size(p: Path) -> str:
    b = p.read_bytes()
    assert b[:8] == b"\x89PNG\r\n\x1a\n", p
    return "%dx%d" % struct.unpack(">II", b[16:24])


def test_manifest_installable():
    m = json.loads((PUB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["name"] and m["short_name"] and m["display"] == "standalone"
    assert m["start_url"] == "/" and m["scope"] == "/" and m["theme_color"] and m["background_color"]
    got = {(i["sizes"], i["purpose"]) for i in m["icons"] if i["type"] == "image/png"}
    assert {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")} <= got
    for i in m["icons"]:
        f = PUB / i["src"].lstrip("/")
        assert f.exists(), i["src"]
        if i["type"] == "image/png":
            assert png_size(f) == i["sizes"], i["src"]


def test_icons_and_share_image_linked():
    site = (WEB / "lib" / "site.ts").read_text(encoding="utf-8")
    assert 'manifest: "/manifest.webmanifest"' in site
    assert png_size(PUB / "icons" / "apple-touch-icon.png") == "180x180"
    assert "apple-touch-icon.png" in site and "summary_large_image" in site
    og = re.search(r'url: "(/og\.jpg)", width: (\d+), height: (\d+)', site)
    assert og and (PUB / og[1].lstrip("/")).exists() and (og[2], og[3]) == ("1200", "630")
    assert "siteMeta" in (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
    for src in re.findall(r'"(/landing/[^"]+)"', (WEB / "components" / "Landing.tsx").read_text(encoding="utf-8")):
        assert (PUB / src.lstrip("/")).exists(), src


def test_service_worker_caches_only_offline_page():
    sw = (PUB / "sw.js").read_text(encoding="utf-8")
    code = "\n".join(l for l in sw.splitlines() if not l.lstrip().startswith("//"))
    # 캐시에 넣는 길은 install 의 c.add(OFFLINE) 하나뿐: put · addAll · 응답 복제(clone) 없음
    assert re.findall(r"\.(put|addAll|add)\(", code) == ["add"]
    assert "c.add(OFFLINE)" in code and 'const OFFLINE = "/offline.html"' in code
    assert "clone(" not in code
    # 화면 이동만 받고, 그 밖의 요청(API · SSE)은 손대지 않음
    assert 'if (e.request.mode !== "navigate") return;' in code
    assert (PUB / "offline.html").exists()
    # Shell 이 등록한다
    assert 'register("/sw.js")' in (WEB / "components" / "Shell.tsx").read_text(encoding="utf-8")


def test_search_only_public_pages():
    sitemap = (WEB / "app" / "sitemap.ts").read_text(encoding="utf-8")
    assert '["", "/privacy"]' in sitemap
    cfg = (WEB / "next.config.ts").read_text(encoding="utf-8")
    src = re.search(r'source: "([^"]+)"', cfg)[1]
    # next.config 의 주소 규칙을 정규식으로 옮겨 어떤 주소가 noindex 인지 본다
    rx = re.compile("^" + src + "$")
    for p in ["/universe", "/history", "/people", "/aspiration", "/settings", "/ops", "/talk/abc"]:
        assert rx.match(p), p
    for p in ["/", "/privacy", "/terms", "/og.jpg", "/sw.js", "/manifest.webmanifest", "/icons/icon-512.png", "/_next/static/x"]:
        assert not rx.match(p), p
