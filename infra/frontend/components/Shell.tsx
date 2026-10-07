"use client";
// 위 막대(휴대폰은 아래 막대) + 로그인 문. 가짜 데이터 모드에서는 로그인을 건너뛴다.
// 초대 목록(백엔드 ALLOWED_EMAILS) 밖 계정이면 403 not_allowed → 안내와 로그아웃만 보인다.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, DEV_LOGIN, getMe, MOCK, supabase } from "@/lib/api";

const NAV = [
  ["/", "쓰기"], ["/universe", "우주"], ["/history", "지난 기록"], ["/people", "사람"], ["/aspiration", "되고 싶은 나"], ["/settings", "설정"],
] as const;

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [state, setState] = useState<"loading" | "in" | "out" | "not_allowed">(MOCK ? "in" : "loading");
  // 화면을 옮기면 맨 위부터(위 막대에 가려 시작하지 않게)
  useEffect(() => { window.scrollTo(0, 0); }, [path]);

  useEffect(() => {
    const sb = supabase();
    if (MOCK || !sb) { if (!MOCK) setState("out"); return; }
    const signedIn = () => getMe().then(() => setState("in"),
      (e) => setState(e instanceof ApiError && e.code === "not_allowed" ? "not_allowed" : "in"));
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
      {state === "in" ? children : state === "out" ? <Login /> : state === "not_allowed" ? (
        <main><div className="card stack" role="alert">
          <h1>초대된 사람만 쓸 수 있어요</h1>
          <p className="sub">이 계정은 아직 초대 목록에 없어요. 운영자에게 알려 주세요.</p>
          <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>
        </div></main>
      ) : <main><p className="sub">불러오는 중…</p></main>}
    </>
  );
}

function Login() {
  const sb = supabase();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  if (!sb) return <main><div className="card"><h1>로그인 설정이 없어요</h1><p className="sub">NEXT_PUBLIC_SUPABASE_URL · NEXT_PUBLIC_SUPABASE_ANON_KEY 를 넣어 주세요.</p></div></main>;
  const google = () => sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });
  const dev = async (e: React.FormEvent) => {
    e.preventDefault();
    const { error } = await sb.auth.signInWithPassword({ email, password: pw });
    setErr(error ? "로그인하지 못했어요. 이메일과 비밀번호를 확인해 주세요." : "");
  };
  return (
    <main>
      <div className="card stack">
        <h1>나의 우주</h1>
        <p className="sub">일기를 생각 단위로 나눠 우주로 보여 주고, 별지기가 말을 걸어요.</p>
        <button className="primary" onClick={google}>구글로 로그인</button>
        {DEV_LOGIN && (
          <form onSubmit={dev} className="stack" aria-label="시험용 계정 로그인">
            <p className="sub">시험용 계정(로컬 전용)</p>
            <div><label htmlFor="em">이메일</label><input id="em" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
            <div><label htmlFor="pw">비밀번호</label><input id="pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></div>
            <button type="submit">시험용 계정으로 들어가기</button>
            {err && <p className="err" role="alert">{err}</p>}
          </form>
        )}
      </div>
    </main>
  );
}
