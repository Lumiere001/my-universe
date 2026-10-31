"use client";
// 틀(PRD v9 휴대폰 전용, 2026-11-01): 머리줄(뒤로 또는 이름 · 제목 · 오른쪽 위 설정) + 아래 탭 넷(이야기 · 일기장 · 우주 · 흐름).
// 화면 폭과 상관없이 같은 틀이다(컴퓨터 화면은 이번에 안 함). 탭 밖 화면(사람 · 되고 싶은 모습 · 설정 · 가져오기 · 운영)은 머리줄 '뒤로'로 돌아간다.
// 로그인 문: 가짜 데이터 모드에서는 로그인을 건너뛴다(동의 확인은 함).
// 초대 목록(백엔드 ALLOWED_EMAILS) 밖 계정이면 403 not_allowed → 안내와 로그아웃만 보인다.
// /privacy(개인정보처리방침) · /terms(이용약관)는 로그인 없이 보인다(구글 OAuth 브랜딩 링크, 정적 HTML 에도 들어감).
// 로그인 뒤 지금 판 동의가 없으면(GET /consent needed) /consent 로 보낸다. 그동안 열리는 화면은 OPEN 뿐(기록 화면은 못 감).
// 백엔드도 동의 없는 기록 만들기를 403 consent_required 로 막는다. 동의 확인이 실패하면 화면은 열고 백엔드가 막는다.
// 로그아웃 상태의 다른 화면은 소개(Landing)를 보인다. 서비스 워커(설치형 웹앱, public/sw.js)는 여기서 등록한다.
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Icon, { type IconName } from "@/components/Icon";
import Landing from "@/components/Landing";
import PrefNotice from "@/components/PrefNotice";
import { KeeperLook } from "@/components/Keeper";
import { ApiError, getConsent, getMe, MOCK, supabase } from "@/lib/api";

// 탭: [주소, 이름, 아이콘, 이 탭에 속한 주소 머리]
const TABS: readonly (readonly [string, string, IconName, readonly string[]])[] = [
  ["/", "이야기", "talk", ["/", "/talk", "/write"]], ["/history", "일기장", "history", ["/history", "/universe/", "/import"]],
  ["/universe", "우주", "universe", ["/universe", "/people", "/aspiration"]], ["/insight", "흐름", "flow", ["/insight"]],
];
const TITLES: Record<string, string> = {
  "/": "이야기", "/talk": "이야기", "/write": "이야기", "/history": "일기장", "/universe": "우주", "/insight": "흐름",
  "/people": "사람", "/aspiration": "되고 싶은 모습", "/settings": "설정", "/import": "지난 일기 가져오기",
  "/consent": "동의 내용", "/privacy": "개인정보처리방침", "/terms": "이용약관", "/ops": "운영",
};
const ROOTS = ["/", "/talk", "/write", "/history", "/universe", "/insight"];   // 뒤로 단추가 없는 화면
const PUBLIC = ["/privacy", "/terms"];
const OPEN = [...PUBLIC, "/consent", "/settings"];   // 동의 전에도 열리는 화면(설정 = 로그아웃 · 계정 지우기)

const titleOf = (path: string) => TITLES[path] ?? (path.startsWith("/universe/") ? "일기" : "");
const tabOf = (path: string) => TABS.find(([, , , heads]) => heads.some((h) => (h.endsWith("/") && h !== "/" ? path.startsWith(h) : path === h)))?.[0];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [state, setState] = useState<"loading" | "in" | "out" | "not_allowed" | "consent">("loading");
  const [intro, setIntro] = useState(false);   // 처음 인터뷰를 아직 안 지남(PRD v9 Q13: 동의 → 되고 싶은 모습 인터뷰 → 첫 대화)
  // 화면을 옮기면 맨 위부터(머리줄에 가려 시작하지 않게)
  useEffect(() => { window.scrollTo(0, 0); }, [path]);
  useEffect(() => { navigator.serviceWorker?.register("/sw.js").catch(() => { /* 설치만 못 할 뿐 */ }); }, []);

  useEffect(() => { if (state === "consent" && !OPEN.includes(path)) router.replace("/consent"); }, [state, path, router]);
  useEffect(() => {
    if (state !== "in" || !intro) return;
    if (path === "/aspiration") { setIntro(false); return; }   // 한 번만 보낸다(나중에 할래요 · 띄우기 뒤 첫 대화로)
    if (!OPEN.includes(path)) router.replace("/aspiration?interview=1");
  }, [state, intro, path, router]);

  useEffect(() => {
    const sb = supabase();
    const consent = () => getConsent().then((c) => setState(c.needed ? "consent" : "in"), () => setState("in"));
    const signedIn = () => getMe().then((me) => { setIntro(me.onboarding.intro === false); return consent(); },
      (e) => setState(e instanceof ApiError && e.code === "not_allowed" ? "not_allowed" : "in"));
    // 가짜 데이터 모드: ?signedout 이면 소개 화면을 본다(로그인은 처음 사람처럼 ?intro 로)
    if (MOCK) { if (new URLSearchParams(window.location.search).has("signedout")) setState("out"); else signedIn(); return; }
    if (!sb) { setState("out"); return; }
    sb.auth.getSession().then(({ data }) => (data.session ? signedIn() : setState("out")));
    // 콜백 안에서 supabase 를 다시 부르면 멈출 수 있어(supabase-js 안내) 한 박자 뒤에 /me 를 본다
    const { data } = sb.auth.onAuthStateChange((_e, s) => { if (s) setTimeout(signedIn, 0); else setState("out"); });
    return () => data.subscription.unsubscribe();
  }, []);

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

  const tab = tabOf(path);
  const root = ROOTS.includes(path);
  // 뒤로: 앱 안에서 왔으면 그 화면으로, 바로 열었으면(알림 · 북마크) 속한 탭으로
  const back = () => (window.history.length > 1 ? router.back() : router.push(tab ?? "/"));
  return (
    <div className="app">
      <KeeperLook />
      <header className="top">
        {root ? <Link href="/" className="brand" aria-label="나의 우주"><i className="dot" aria-hidden /></Link>
          : <button className="icon" onClick={back} aria-label="뒤로"><Icon name="back" size={22} /></button>}
        <span className="top-title">{titleOf(path)}</span>
        {path !== "/settings" && <Link className="icon-link" href="/settings" aria-label="설정"><Icon name="settings" size={20} /></Link>}
      </header>
      {page}
      <PrefNotice />
      <nav className="tabbar" aria-label="탭">
        {TABS.map(([href, name, icon]) => (
          <Link key={href} href={href} aria-current={tab === href ? "page" : undefined}><Icon name={icon} size={22} />{name}</Link>
        ))}
      </nav>
    </div>
  );
}
