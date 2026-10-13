"use client";
// 위 막대(휴대폰은 아래 막대) + 로그인 문. 가짜 데이터 모드에서는 로그인을 건너뛴다(동의 확인은 함).
// 초대 목록(백엔드 ALLOWED_EMAILS) 밖 계정이면 403 not_allowed → 안내와 로그아웃만 보인다.
// /privacy(개인정보처리방침) · /terms(이용약관)는 로그인 없이 보인다(구글 OAuth 브랜딩 링크, 정적 HTML 에도 들어감).
// 로그인 뒤 지금 판 동의가 없으면(GET /consent needed) /consent 로 보낸다. 그동안 열리는 화면은 OPEN 뿐(기록 화면은 못 감).
// 백엔드도 동의 없는 기록 만들기를 403 consent_required 로 막는다. 동의 확인이 실패하면 화면은 열고 백엔드가 막는다.
// 로그아웃 상태의 다른 화면은 소개(Landing)를 보인다. 서비스 워커(설치형 웹앱, public/sw.js)는 여기서 등록한다.
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Landing from "@/components/Landing";
import { KeeperLook } from "@/components/Keeper";
import { ApiError, getConsent, getMe, MOCK, supabase } from "@/lib/api";

const NAV = [
  ["/talk", "이야기하기"], ["/", "직접 쓰기"], ["/universe", "우주"], ["/history", "지난 기록"], ["/people", "사람"], ["/aspiration", "되고 싶은 나"], ["/settings", "설정"],
] as const;
const PUBLIC = ["/privacy", "/terms"];
const OPEN = [...PUBLIC, "/consent", "/settings"];   // 동의 전에도 열리는 화면(설정 = 로그아웃 · 계정 지우기)

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [state, setState] = useState<"loading" | "in" | "out" | "not_allowed" | "consent">("loading");
  // 화면을 옮기면 맨 위부터(위 막대에 가려 시작하지 않게)
  useEffect(() => { window.scrollTo(0, 0); }, [path]);
  useEffect(() => { navigator.serviceWorker?.register("/sw.js").catch(() => { /* 설치만 못 할 뿐 */ }); }, []);

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

  return (
    <>
      <header className="top">
        <Link href="/" className="brand">나의 우주</Link>
        {state === "in" && (
          <nav className="nav" aria-label="화면">
            {NAV.map(([href, name]) => (
              <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>{name}</Link>
            ))}
          </nav>
        )}
      </header>
      {state === "in" && <KeeperLook />}
      {state === "in" || PUBLIC.includes(path) || (state === "consent" && OPEN.includes(path)) ? children
        : state === "out" ? <Landing /> : state === "not_allowed" ? (
        <main><div className="card stack" role="alert">
          <h1>초대된 사람만 쓸 수 있어요</h1>
          <p className="sub">이 계정은 아직 초대 목록에 없어요. 운영자에게 알려 주세요.</p>
          <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>
        </div></main>
      ) : <main><p className="sub">불러오는 중…</p></main>}
    </>
  );
}
