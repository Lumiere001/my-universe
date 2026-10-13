"use client";
// 로그인 전 첫 화면(소개). Shell 이 로그아웃 상태에서 보여 주고, 로그인하면 Shell 이 바로 앱 화면을 연다.
// 화면 캡처는 로컬 시험 계정 tester@ 의 하늘 데모 우주(가상 인물) — scripts/make-images.mjs 가 만든다.
import Link from "next/link";
import { useState } from "react";
import InstallGuide from "@/components/InstallGuide";
import { DEV_LOGIN, supabase } from "@/lib/api";

const STEPS = [
  ["쓰기 · 이야기하기", "오늘 있었던 일, 떠오른 생각, 다짐을 마음껏 적어요. 마음 날씨는 골라도 되고 건너뛰어도 돼요.", "/landing/write.jpg", 390, 668],
  ["우주", "별지기가 글을 생각 단위로 나눠 삶의 영역(해) 곁에 행성으로 띄워요. 지난 생각과 이어지면 선이 생겨요.", "/landing/universe-mobile.jpg", 390, 624],
  ["별지기 한마디", "지난 기록을 기억하는 별지기가 오늘 글에 맞춰 말을 걸어요. 말투는 다정하게부터 팩폭까지 골라요.", "/landing/message.jpg", 390, 316],
] as const;

export default function Landing() {
  const sb = supabase();
  const google = () => sb?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });
  const start = sb ? <button className="primary" onClick={google}>구글로 시작하기</button>
    : <p className="err">로그인 설정이 없어요. NEXT_PUBLIC_SUPABASE_URL · NEXT_PUBLIC_SUPABASE_ANON_KEY 를 넣어 주세요.</p>;

  return (
    <main className="wide landing">
      <section className="hero" aria-label="소개">
        <div className="stack">
          <h1>나의 우주</h1>
          <p className="lead">일기를 쓰면 생각 단위로 나눠 나만의 우주에 띄우고, 별지기가 지난 기록을 기억해 말을 걸어요.</p>
          {start}
          <p className="sub">구글 계정이면 누구나 바로 시작해요. 지금은 시험 단계예요.</p>
        </div>
        <img src="/landing/universe.jpg" width={1246} height={748} alt="일기로 만든 우주 화면. 삶의 영역마다 해가 있고, 그 곁을 기록 행성이 돌며 생각끼리 선으로 이어져 있어요." />
      </section>

      <section aria-labelledby="how">
        <h2 id="how">쓰는 법</h2>
        <ol className="how">
          {STEPS.map(([name, text, src, w, h], i) => (
            <li key={name} className="card">
              <h3><span className="badge v">{i + 1}</span> {name}</h3>
              <p className="sub">{text}</p>
              <img src={src} width={w} height={h} loading="lazy" alt={`${name} 화면`} />
            </li>
          ))}
        </ol>
      </section>

      <section className="card" aria-labelledby="promise">
        <h2 id="promise">개인정보 약속</h2>
        <ul>
          <li>일기 원문은 사용자마다 다른 키로 <b>암호화</b>해 저장해요. 다른 사용자는 내 기록을 볼 수 없어요.</li>
          <li>외부 AI로 보낼 때는 사람 이름을 <b>가명</b>으로 바꿔 보내요.</li>
          <li>광고 · 방문 분석 도구를 쓰지 않아요.</li>
          <li>설정에서 언제든 <b>계정과 모든 기록을 지울</b> 수 있어요.</li>
          <li>서버가 화면에 글을 보여 주려면 풀어야 해서, 운영자는 기술적으로 읽을 수 있어요. 읽지 않는 것이 우리의 약속이에요.</li>
        </ul>
        <p style={{ margin: 0 }}><Link href="/privacy">개인정보처리방침 자세히 보기</Link></p>
      </section>

      <section className="card" aria-labelledby="beta">
        <h2 id="beta">시험 단계 안내</h2>
        <p style={{ margin: 0 }}>나의 우주는 지금 시험 운영 중이에요. 기능과 화면이 자주 바뀔 수 있어요.
          일기를 돌아보도록 돕는 도구이고, 의료 · 상담 서비스가 아니에요. 불편한 점은 화면 안 &apos;불편한 점 한 줄&apos;로 알려 주세요.</p>
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
