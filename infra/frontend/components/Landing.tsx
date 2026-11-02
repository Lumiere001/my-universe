"use client";
// 로그인 전 첫 화면. Shell 이 로그아웃 상태에서 머리줄 없이 보여 주고, 로그인하면 바로 앱 화면을 연다.
// 두 모습(2026-11-02 동규 「전용 앱에서 쓰는 것에 맞춰 · 처음 받을 때 쓸 랜딩 페이지」):
//  브라우저로 연 사람 = 앱 받기 화면(무엇인지 한 줄 · 화면 세 장 · 홈 화면에 앱으로 받는 법, 설치 없이 시작은 작은 링크)
//  홈 화면 앱으로 연 사람 = 시작 화면(화면 세 장 · 구글로 시작). 화면 캡처는 scripts/make-images.mjs 가 만든다.
import Link from "next/link";
import { useEffect, useState } from "react";
import InstallGuide, { platform, type Platform } from "@/components/InstallGuide";
import { DEV_LOGIN, MOCK, supabase } from "@/lib/api";
import { SITE } from "@/lib/site";

const CARDS = [
  ["별지기와 이야기해요", "오늘 있었던 일을 말하면, 내 말로 일기 한 편을 정리해 줘요.", "/landing/write.jpg", 390, 668],
  ["생각이 우주가 돼요", "일기 속 생각이 별이 되어 지난 생각과 이어져요.", "/landing/universe-mobile.jpg", 390, 624],
  ["내 일기는 나만 봐요", "암호화해 두고, AI에는 이름을 가명으로 바꿔 보내요.", "/landing/message.jpg", 390, 230],
] as const;

export default function Landing() {
  const sb = supabase();
  const [where, setWhere] = useState<Platform | null>(null);   // 그리기 전에는 모름(서버 그림과 어긋나지 않게)
  const [fail, setFail] = useState(false);
  useEffect(() => setWhere(platform()), []);
  const google = async () => {
    setFail(false);
    const r = await sb?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } }).catch(() => null);
    if (!r || r.error) setFail(true);
  };
  const app = where === "installed";
  const start = (cls: string) => MOCK ? <a className={cls} href="/?intro">구글로 시작하기</a>
    : sb ? <button className={cls} onClick={google}>구글로 시작하기</button>
    : <p className="err">로그인 설정이 없어요. NEXT_PUBLIC_SUPABASE_URL · NEXT_PUBLIC_SUPABASE_ANON_KEY 를 넣어 주세요.</p>;

  return (
    <main className="landing">
      <header className="land-hero">
        <img src="/icons/icon-192.png" width={72} height={72} alt="" />
        <h1>나의 우주</h1>
        <p>말하듯 쓰는 일기, 생각이 우주가 돼요.</p>
        {app ? start("btn primary wide") : <a className="btn primary wide" href="#get">앱 받기</a>}
        {fail && <p className="err" role="alert">구글 로그인을 열지 못했어요. 잠시 뒤 다시 눌러 주세요.</p>}
      </header>

      <ol className="intro-cards" aria-label="옆으로 넘겨 보세요">
        {CARDS.map(([name, text, src, w, h], i) => (
          <li key={name}>
            <img src={src} width={w} height={h} loading={i ? "lazy" : undefined} alt={`${name} 화면`} />
            <h2>{name}</h2>
            <p>{text}</p>
          </li>
        ))}
      </ol>

      {!app && where && (
        <section id="get" className="land-get" aria-labelledby="get-h">
          <h2 id="get-h">앱 받기</h2>
          {where === "other"
            ? <p>휴대폰에서 <b>{SITE.replace(/^https?:\/\//, "")}</b> 를 열면 앱으로 받을 수 있어요.</p>
            : <InstallGuide bare />}
          <p className="sub">스토어 없이 바로 받아요. 홈 화면의 나의 우주를 누르면 앱으로 열려요.</p>
        </section>
      )}

      {!app && (
        <p className="land-alt">설치 없이 써 보려면 {MOCK ? <a href="/?intro">구글로 시작하기</a>
          : sb && <button className="link inline" onClick={google}>구글로 시작하기</button>}</p>
      )}
      {DEV_LOGIN && sb && <DevLogin />}

      <footer className="land-foot sub">
        시험 운영 중이에요 · <Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link>
      </footer>
    </main>
  );
}

// 시험용 계정 로그인(로컬 전용, NEXT_PUBLIC_DEV_LOGIN=1). 비밀번호 또는 메일 코드(로컬 메일함의 여섯 자리) —
// 홈 화면 앱은 사파리와 저장소가 따로라, 붙여넣기가 안 되는 시뮬레이터에서도 비밀번호 없이 들어가게
function DevLogin() {
  const sb = supabase()!;
  const [email, setEmail] = useState(process.env.NEXT_PUBLIC_DEV_EMAIL ?? "");   // 로컬 .env.local 의 시험 계정(홈 화면 앱에서 다시 치지 않게)
  const [pw, setPw] = useState("");
  const [code, setCode] = useState<string | null>(null);   // null = 비밀번호로, 문자열 = 코드 칸
  const [err, setErr] = useState("");
  const done = (error: unknown) => setErr(error ? "로그인하지 못했어요. 이메일과 비밀번호(코드)를 확인해 주세요." : "");
  const dev = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code === null) done((await sb.auth.signInWithPassword({ email, password: pw })).error);
    else done((await sb.auth.verifyOtp({ email, token: code, type: "email" })).error);
  };
  const ask = async () => {
    const { error } = await sb.auth.signInWithOtp({ email, options: { shouldCreateUser: false } });
    if (error) done(error); else { setErr(""); setCode(""); }
  };
  return (
    <form onSubmit={dev} className="card stack" aria-label="시험용 계정 로그인">
      <p className="sub">시험용 계정(로컬 전용)</p>
      <div><label htmlFor="em">이메일</label><input id="em" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
      {code === null ? (
        <div><label htmlFor="pw">비밀번호</label><input id="pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></div>
      ) : (
        <div><label htmlFor="code">메일로 받은 코드</label><input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.trim())} required /></div>
      )}
      <div className="row">
        <button type="submit">시험용 계정으로 들어가기</button>
        {code === null && <button type="button" className="link" disabled={!email} onClick={ask}>메일 코드로</button>}
      </div>
      {err && <p className="err" role="alert">{err}</p>}
    </form>
  );
}
