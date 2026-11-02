"use client";
// 로그인 전 첫 화면. Shell 이 로그아웃 상태에서 머리줄 없이 보여 주고, 로그인하면 바로 앱 화면을 연다.
// 디자인(2026-11-02 동규 「부가티 디자인 + 약간의 우주 느낌」, getdesign.md/bugatti): 검은 바탕 · 흰 글자 · 넓은 자간 ·
// 투명한 알약 버튼 · 굵은 글자 없음 · 둥근 모서리는 버튼만. 사진 자리는 흑백(먹 테마) 우주, 바탕엔 옅은 별가루, 받기 칸엔 궤도 하나.
//  브라우저로 연 사람 = 앱 받기 화면(맨 위 우주 → 하는 일 셋 → 약속 셋 → 받는 법)
//  홈 화면 앱으로 연 사람 = 처음이면 카드뉴스(CardNews), 다음은 시작 화면(우주 · 구글로 시작). 사진은 scripts/make-images.mjs 가 찍는다.
import { Gowun_Batang, IBM_Plex_Mono, Saira_Condensed } from "next/font/google";
import Link from "next/link";
import { useEffect, useState } from "react";
import CardNews from "@/components/CardNews";
import InstallGuide, { platform, type Platform } from "@/components/InstallGuide";
import { DEV_LOGIN, MOCK, supabase } from "@/lib/api";
import { SITE } from "@/lib/site";

// 부가티 세 글꼴의 대체(DESIGN.md 권고): 제목 = Saira Condensed(한글은 기기 고딕), 본문 = 명조(고운바탕), 버튼 · 작은 글 = IBM Plex Mono
const display = Saira_Condensed({ weight: "400", subsets: ["latin"], variable: "--lux-display" });
const serif = Gowun_Batang({ weight: "400", variable: "--lux-serif", display: "swap", preload: false });
const mono = IBM_Plex_Mono({ weight: "400", subsets: ["latin"], variable: "--lux-mono" });
const FONTS = `${display.variable} ${serif.variable} ${mono.variable}`;

const MODELS = [
  ["01 — TALK", "별지기와 이야기해요", "오늘 있었던 일을 말하면, 별지기가 묻고 들은 뒤 내 말로 일기 한 편을 정리해 줘요.", "/landing/talk.jpg"],
  ["02 — DIARY", "일기장에 남겨요", "내가 한 말과 별지기의 정리를 나란히 두고, 틀린 곳은 바로 고쳐요.", "/landing/write.jpg"],
  ["03 — UNIVERSE", "생각이 우주가 돼요", "일기 속 생각이 별이 되어 지난 생각과 이어지고, 한 갈래 이야기가 쌓이면 새 해가 떠요.", "/landing/universe-mobile.jpg"],
] as const;
const SPECS = [
  ["10편", "한 갈래 이야기가 10편 쌓이면 우주에 새 해가 떠요"],
  ["AES-GCM", "일기는 사람마다 다른 열쇠로 잠가 둬요"],
  ["가명", "AI에는 사람 이름을 가명으로 바꿔 보내요"],
] as const;
const SEEN = "cards-seen";   // 카드뉴스를 본 기기(이 기기 편의용, 못 읽으면 다시 보여 줌)

export default function Landing() {
  const sb = supabase();
  const [where, setWhere] = useState<Platform | null>(null);   // 그리기 전에는 모름(서버 그림과 어긋나지 않게)
  const [cards, setCards] = useState(false);
  const [fail, setFail] = useState(false);
  useEffect(() => {
    const p = platform();
    setWhere(p);
    let seen = false;
    try { seen = !!localStorage.getItem(SEEN); } catch { /* 저장소를 못 쓰면 처음처럼 */ }
    if ((p === "installed" && !seen) || new URLSearchParams(location.search).has("cards")) setCards(true);
  }, []);
  const google = async () => {
    setFail(false);
    const r = await sb?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } }).catch(() => null);
    if (!r || r.error) setFail(true);
  };
  const app = where === "installed";
  const start = (cls: string) => MOCK ? <a className={cls} href="/?intro">구글로 시작하기</a>
    : sb ? <button className={cls} onClick={google}>구글로 시작하기</button>
    : <p className="err">로그인 설정이 없어요. NEXT_PUBLIC_SUPABASE_URL · NEXT_PUBLIC_SUPABASE_ANON_KEY 를 넣어 주세요.</p>;

  if (cards) return <CardNews onDone={() => { try { localStorage.setItem(SEEN, "1"); } catch { /* 다음에 또 보임 */ } setCards(false); }} />;

  return (
    <main className={`lux ${FONTS}`}>
      <nav className="lux-nav" aria-label="나의 우주">
        <span className="lux-cap lux-wide">A TALKING DIARY</span>
        <span className="lux-mark">MY UNIVERSE</span>
        {!app && <a className="lux-navlink" href="#get">앱 받기</a>}
      </nav>

      <header className="lux-hero">
        <picture>
          <source media="(min-width: 768px)" srcSet="/landing/hero.jpg" />
          <img src="/landing/hero-mobile.jpg" alt="흰 해와 별이 떠 있는 검은 우주" />
        </picture>
        <div className="lux-hero-text">
          <p className="lux-cap">말하듯 쓰는 일기</p>
          <h1>나의 우주</h1>
          <p className="lux-lead">오늘 하루를 이야기하면, 생각이 별이 되어 나만의 우주가 돼요.</p>
        </div>
        <div className="lux-hero-cta">
          {app ? start("lux-btn") : <a className="lux-btn" href="#get">앱 받기</a>}
          {fail && <p className="err" role="alert">구글 로그인을 열지 못했어요. 잠시 뒤 다시 눌러 주세요.</p>}
        </div>
      </header>

      {!app && <>
        <section className="lux-models" aria-label="나의 우주에서 하는 일">
          {MODELS.map(([cap, name, text, src]) => (
            <article key={name} className="lux-model">
              <img src={src} alt={`${name} 화면`} loading="lazy" />
              <p className="lux-cap">{cap}</p>
              <h2>{name}</h2>
              <p className="lux-body">{text}</p>
            </article>
          ))}
        </section>

        <section className="lux-specs" aria-label="약속">
          <dl>
            {SPECS.map(([v, d]) => <div key={v}><dt>{v}</dt><dd>{d}</dd></div>)}
          </dl>
        </section>

        <section id="get" className="lux-get" aria-labelledby="get-h">
          <div className="lux-orbit" aria-hidden><i /></div>
          <p className="lux-cap">GET THE APP</p>
          <h2 id="get-h">지금, 홈 화면에</h2>
          {where === "other" && (   // 컴퓨터로 연 사람: 휴대폰 카메라로 QR(public/landing/qr.svg, segno 로 한 번 만듦 · 주소가 바뀌면 다시)
            <div className="lux-qr">
              <img src="/landing/qr.svg" width={132} height={132} alt="나의 우주 주소 QR 코드" />
              <p className="lux-body">휴대폰 카메라로 비추면 바로 열려요</p>
              <p className="lux-addr">{SITE.replace(/^https?:\/\//, "")}</p>
            </div>
          )}
          {where && <div className="lux-install"><InstallGuide bare /></div>}
          <p className="lux-body lux-muted">스토어 없이 바로 받아요. 홈 화면의 나의 우주를 누르면 앱으로 열려요.</p>
          <p className="lux-alt">설치 없이 써 보려면 {MOCK ? <a href="/?intro">구글로 시작하기</a>
            : sb && <button className="lux-textlink" onClick={google}>구글로 시작하기</button>}</p>
        </section>
      </>}
      {DEV_LOGIN && sb && <DevLogin />}

      <footer className="lux-foot">
        <p>시험 운영 중이에요 · <Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link></p>
        <span className="lux-mark">MY UNIVERSE</span>
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
    <form onSubmit={dev} className="card stack lux-dev" aria-label="시험용 계정 로그인">
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
