"use client";
// 로그인 전 첫 화면(소개). Shell 이 로그아웃 상태에서 보여 주고, 로그인하면 Shell 이 바로 앱 화면을 연다.
// PRD v9 Q13: 휴대폰에서 넘기는 카드 세 장(무엇을 해 주나 · 우주 · 내 일기를 지키는 법) → 구글로 시작. 자세한 약속은 그 아래.
// 화면 캡처는 가짜 데이터 모드의 가상 인물 하늘 화면(지금 디자인) — scripts/make-images.mjs 가 만든다.
import Link from "next/link";
import { useState } from "react";
import InstallGuide from "@/components/InstallGuide";
import { DEV_LOGIN, MOCK, supabase } from "@/lib/api";

const CARDS = [
  ["별지기가 먼저 말을 걸어요", "앱을 열면 별지기가 가볍게 말을 걸어요. 편하게 이야기하면 내가 한 말로 일기 한 편을 정리해 드려요. 글 · 사진 · 말로 직접 써도 돼요.", "/landing/write.jpg", 390, 668],
  ["생각이 우주가 돼요", "일기 속 생각이 행성이 되어 삶의 영역 곁을 돌아요. 지난 생각과 이어지고 바뀐 흐름을 원문 그대로 비춰 줘요.", "/landing/universe-mobile.jpg", 390, 624],
  ["내 일기는 나만 봐요", "일기는 사람마다 다른 키로 암호화해 두고, AI에는 사람 이름을 가명으로 바꿔 보내요. 언제든 모든 기록을 지울 수 있어요.", "/landing/message.jpg", 390, 230],
] as const;

export default function Landing() {
  const sb = supabase();
  const [fail, setFail] = useState(false);
  const google = async () => {
    setFail(false);
    const r = await sb?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } }).catch(() => null);
    if (!r || r.error) setFail(true);
  };
  const start = MOCK ? <a className="btn primary" href="/?intro">구글로 시작하기</a> : sb ? <>
    <button className="primary" onClick={google}>구글로 시작하기</button>
    {fail && <p className="err" role="alert">구글 로그인을 열지 못했어요. 잠시 뒤 다시 눌러 주세요.</p>}
  </> : <p className="err">로그인 설정이 없어요. NEXT_PUBLIC_SUPABASE_URL · NEXT_PUBLIC_SUPABASE_ANON_KEY 를 넣어 주세요.</p>;

  return (
    <main className="wide landing">
      <section className="intro stack" aria-label="소개">
        <h1>나의 우주</h1>
        <p className="lead">말하듯 남긴 일기가 쌓이면, 지난 기록 속에서 내 생각이 어떻게 이어지고 바뀌어 왔는지 비춰 줘요.</p>
        <ol className="intro-cards" aria-label="처음 쓰는 분께, 옆으로 넘겨 보세요">
          {CARDS.map(([name, text, src, w, h], i) => (
            <li key={name} className="card">
              <h2><span className="badge v">{i + 1}</span> {name}</h2>
              <p className="sub">{text}</p>
              <img src={src} width={w} height={h} loading={i ? "lazy" : undefined} alt={`${name} 화면`} />
            </li>
          ))}
        </ol>
        {start}
        <p className="sub">구글 계정이면 누구나 바로 시작해요. 지금은 시험 단계예요.</p>
      </section>

      <section className="card" aria-labelledby="promise">
        <h2 id="promise">개인정보 약속</h2>
        <ul>
          <li>일기 원문은 사용자마다 다른 키로 <b>암호화</b>해 저장해요. 다른 사용자는 내 기록을 볼 수 없어요.</li>
          <li>일기를 정리하고 말을 거는 외부 AI에는 사람 이름을 <b>가명</b>으로 바꿔 보내요. 사진 · 음성으로 쓸 때는 글자 읽기 · 받아쓰기 업체에 원본이 가요.</li>
          <li>광고 · 방문 분석 도구를 쓰지 않아요.</li>
          <li>설정에서 언제든 <b>계정과 모든 기록을 지울</b> 수 있어요.</li>
          <li>서버가 화면에 글을 보여 주려면 풀어야 해서, 운영자는 기술적으로 읽을 수 있어요. 직접 동의한 피드백 말고는 읽지 않는 것이 우리의 약속이에요.</li>
        </ul>
        <p style={{ margin: 0 }}><Link href="/privacy">개인정보처리방침 자세히 보기</Link></p>
      </section>

      <section className="card" aria-labelledby="beta">
        <h2 id="beta">시험 단계 안내</h2>
        <p style={{ margin: 0 }}>나의 우주는 지금 시험 운영 중이에요. 기능과 화면이 자주 바뀔 수 있어요.
          일기를 돌아보도록 돕는 도구이고, 의료 · 상담 서비스가 아니에요. 불편한 점은 정리한 결과나 설정의 &apos;불편한 점 한 줄&apos;로 알려 주세요.</p>
      </section>

      <InstallGuide />

      <section className="card stack" aria-label="시작하기">
        <h2>내 우주 만들기</h2>
        {start}
        {DEV_LOGIN && sb && <DevLogin />}
      </section>

      <p className="sub"><Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link></p>
    </main>
  );
}

// 시험용 계정 로그인(로컬 전용, NEXT_PUBLIC_DEV_LOGIN=1)
function DevLogin() {
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const dev = async (e: React.FormEvent) => {
    e.preventDefault();
    const { error } = await supabase()!.auth.signInWithPassword({ email, password: pw });
    setErr(error ? "로그인하지 못했어요. 이메일과 비밀번호를 확인해 주세요." : "");
  };
  return (
    <form onSubmit={dev} className="stack" aria-label="시험용 계정 로그인">
      <p className="sub">시험용 계정(로컬 전용)</p>
      <div><label htmlFor="em">이메일</label><input id="em" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
      <div><label htmlFor="pw">비밀번호</label><input id="pw" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></div>
      <button type="submit">시험용 계정으로 들어가기</button>
      {err && <p className="err" role="alert">{err}</p>}
    </form>
  );
}
