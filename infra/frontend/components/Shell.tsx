"use client";
// 틀(옵시디언 느낌, docs/DESIGN.md): PC는 왼쪽 사이드바(메뉴 + 작은 달력 · 최근 기록) + 머리줄, 휴대폰은 머리줄 + 아래 막대(자주 쓰는 4개) + 서랍.
// 로그인 문: 가짜 데이터 모드에서는 로그인을 건너뛴다(동의 확인은 함).
// 초대 목록(백엔드 ALLOWED_EMAILS) 밖 계정이면 403 not_allowed → 안내와 로그아웃만 보인다.
// /privacy(개인정보처리방침) · /terms(이용약관)는 로그인 없이 보인다(구글 OAuth 브랜딩 링크, 정적 HTML 에도 들어감).
// 로그인 뒤 지금 판 동의가 없으면(GET /consent needed) /consent 로 보낸다. 그동안 열리는 화면은 OPEN 뿐(기록 화면은 못 감).
// 백엔드도 동의 없는 기록 만들기를 403 consent_required 로 막는다. 동의 확인이 실패하면 화면은 열고 백엔드가 막는다.
// 로그아웃 상태의 다른 화면은 소개(Landing)를 보인다. 서비스 워커(설치형 웹앱, public/sw.js)는 여기서 등록한다.
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import Calendar, { countByDay, dayOf, useEntries } from "@/components/Calendar";
import Icon, { type IconName } from "@/components/Icon";
import Landing from "@/components/Landing";
import { KeeperLook } from "@/components/Keeper";
import { ApiError, getConsent, getMe, MOCK, supabase } from "@/lib/api";

const NAV: readonly (readonly [string, string, IconName])[] = [
  ["/", "이야기하기", "talk"], ["/write", "직접 쓰기", "write"], ["/universe", "우주", "universe"], ["/history", "지난 기록", "history"],
  ["/people", "사람", "people"], ["/aspiration", "되고 싶은 모습", "north"], ["/settings", "설정", "settings"],
];
const TABS = NAV.slice(0, 4);   // 휴대폰 아래 막대
const TITLES: Record<string, string> = { "/talk": "이야기하기", "/import": "지난 일기 가져오기", "/consent": "동의 내용", "/privacy": "개인정보처리방침", "/terms": "이용약관", "/ops": "운영" };
const PUBLIC = ["/privacy", "/terms"];
const OPEN = [...PUBLIC, "/consent", "/settings"];   // 동의 전에도 열리는 화면(설정 = 로그아웃 · 계정 지우기)
const FOLD = "side-collapsed";   // PC에서 사이드바를 접어 둔 것(이 기기에만)

const titleOf = (path: string) => TITLES[path] ?? NAV.find(([h]) => h === path)?.[1] ?? (path.startsWith("/universe/") ? "우주 › 기록" : "");
const RECENT = 5;   // 사이드바 최근 기록 수

// 사이드바 '지난 기록'(C-01): 작은 달력(옵시디언 달력 플러그인처럼, 기록 있는 날에 점) + 최근 기록 다섯 편.
// 처음 한 번 읽고, 기록이 바뀌면(lib/api.ts 의 'entries' 알림)만 다시 읽는다(useEntries, 지난 기록 화면과 같은 한 번의 읽기).
// 날을 누르면 /history?day= 로 그날을 고른 지난 기록. 지난 기록을 보는 중이면 거기서 고른 날 · 연 기록을 같이 보인다.
function Recent({ onPick }: { onPick: () => void }) {
  const path = usePathname();
  const router = useRouter();
  const q = useSearchParams();
  const here = path === "/history";
  const open = here ? q.get("id") : null;
  const [list, err] = useEntries();
  const opened = list?.find((e) => e.id === open);
  const selected = here ? q.get("day") ?? (opened ? dayOf(opened) : null) : null;
  return (
    <details className="side-sec" open>
      <summary>지난 기록</summary>
      <Calendar compact marks={list ? countByDay(list) : {}} selected={selected}
        onPick={(d) => { router.push(`/history?day=${d}`); onPick(); }} />
      <h2 className="side-title">최근 기록</h2>
      <div className="tree">
        {err && <p className="none">{err}</p>}
        {list?.length === 0 && <p className="none">아직 남긴 기록이 없어요.</p>}
        {list?.slice(0, RECENT).map((e) => (
          <Link key={e.id} href={`/history?id=${encodeURIComponent(e.id)}`} title={e.title} onClick={onPick}
            aria-current={e.id === open ? "page" : undefined}>
            <Icon name="file" size={15} /><span>{e.title || "제목 없는 글"}</span>
          </Link>
        ))}
        {(list?.length ?? 0) > RECENT && <Link className="more" href="/history" onClick={onPick}>모든 기록 보기</Link>}
      </div>
    </details>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [state, setState] = useState<"loading" | "in" | "out" | "not_allowed" | "consent">("loading");
  const [drawer, setDrawer] = useState(false);       // 휴대폰 서랍
  const [folded, setFolded] = useState(false);       // PC 사이드바 접힘
  // 화면을 옮기면 맨 위부터(머리줄에 가려 시작하지 않게), 서랍은 닫는다
  useEffect(() => { window.scrollTo(0, 0); setDrawer(false); }, [path]);
  useEffect(() => { navigator.serviceWorker?.register("/sw.js").catch(() => { /* 설치만 못 할 뿐 */ }); }, []);
  useEffect(() => { try { setFolded(localStorage.getItem(FOLD) === "1"); } catch { /* 저장소 막힘 */ } }, []);
  useEffect(() => {
    if (!drawer) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setDrawer(false); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [drawer]);

  useEffect(() => { if (state === "consent" && !OPEN.includes(path)) router.replace("/consent"); }, [state, path, router]);

  useEffect(() => {
    const sb = supabase();
    const consent = () => getConsent().then((c) => setState(c.needed ? "consent" : "in"), () => setState("in"));
    const signedIn = () => getMe().then(consent,
      (e) => setState(e instanceof ApiError && e.code === "not_allowed" ? "not_allowed" : "in"));
    if (MOCK) { consent(); return; }
    if (!sb) { setState("out"); return; }
    sb.auth.getSession().then(({ data }) => (data.session ? signedIn() : setState("out")));
    // 콜백 안에서 supabase 를 다시 부르면 멈출 수 있어(supabase-js 안내) 한 박자 뒤에 /me 를 본다
    const { data } = sb.auth.onAuthStateChange((_e, s) => { if (s) setTimeout(signedIn, 0); else setState("out"); });
    return () => data.subscription.unsubscribe();
  }, []);

  // 머리줄 단추: 휴대폰은 서랍을 열고, PC는 사이드바를 접거나 편다
  const toggle = () => {
    if (window.matchMedia("(max-width: 899px)").matches) return setDrawer(!drawer);
    const next = !folded;
    setFolded(next);
    try { localStorage.setItem(FOLD, next ? "1" : "0"); } catch { /* 저장소 막힘 */ }
  };

  const page = state === "in" || PUBLIC.includes(path) || (state === "consent" && OPEN.includes(path)) ? children
    : state === "out" ? <Landing /> : state === "not_allowed" ? (
      <main><div className="card stack" role="alert">
        <h1>초대된 사람만 쓸 수 있어요</h1>
        <p className="sub">이 구글 계정은 아직 초대 목록에 없어요. 초대받은 계정으로 다시 로그인하거나, 운영자에게 알려 주세요.</p>
        <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>
      </div></main>
    ) : <main><p className="sub">로그인을 확인하는 중…</p></main>;

  // 로그인 전 · 동의 전: 틀 없이 이름 줄만
  if (state !== "in") return (
    <>
      <header className="top"><Link href="/" className="brand"><i className="dot" aria-hidden />나의 우주</Link></header>
      {page}
    </>
  );

  const title = titleOf(path);
  return (
    <div className="app" data-drawer={drawer || undefined} data-collapsed={folded || undefined}>
      <KeeperLook />
      <aside className="side" aria-label="사이드바">
        <div className="side-head">
          <Link href="/" className="brand"><i className="dot" aria-hidden />나의 우주</Link>
          <button className="icon only-phone" onClick={() => setDrawer(false)} aria-label="메뉴 닫기"><Icon name="close" /></button>
        </div>
        <div className="side-body">
          <nav className="nav" aria-label="메뉴">
            {NAV.map(([href, name, icon]) => (
              <Link key={href} href={href} aria-current={path === href ? "page" : undefined} onClick={() => setDrawer(false)}><Icon name={icon} />{name}</Link>
            ))}
          </nav>
          <Suspense fallback={null}><Recent onPick={() => setDrawer(false)} /></Suspense>
        </div>
      </aside>
      <div className="scrim" onClick={() => setDrawer(false)} aria-hidden />
      <div className="work">
        <header className="top">
          <button className="icon" onClick={toggle} aria-label="메뉴 열기 · 닫기">
            <Icon name="sidebar" />
          </button>
          <span className="crumb">나의 우주{title && <> › <b>{title}</b></>}</span>
        </header>
        {page}
      </div>
      <nav className="tabbar" aria-label="바로 가기">
        {TABS.map(([href, name, icon]) => (
          <Link key={href} href={href} aria-current={path === href ? "page" : undefined}><Icon name={icon} size={22} />{name}</Link>
        ))}
      </nav>
    </div>
  );
}
