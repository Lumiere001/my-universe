"use client";
// 첫 로그인 동의(WS24). Shell 이 지금 판 동의가 없으면 여기로 보낸다. 이미 동의한 사람은 선택 동의를 바꾸러 온다.
// 판 번호는 백엔드 app/api/consent.py VERSION. 이 화면 · /privacy · /terms 문구를 바꾸면 그 VERSION 을 올린다(모두에게 다시 물음).
// 위기 대응 안내(단체 · 번호)는 넣지 않는다(시험 단계 방침, 2026-10-08 동규).
import Link from "next/link";
import { useEffect, useState } from "react";
import Contact from "@/components/Contact";
import { getConsent, MOCK, saveConsent, supabase, why, type Consent } from "@/lib/api";

const UL = { margin: 0, paddingLeft: 20 } as const;
const BOX = { width: "auto", marginTop: 4, flex: "none" } as const;

// 외부로 나가는 곳 — /privacy 5장과 같은 내용(바꾸면 둘 다)
const OUT: [string, string, string][] = [
  ["Upstage Studio · Solar", "가명으로 바꾼 일기 글(정리 · 말 걸기 · 마음 살피기 · 벡터 만들기)", "글을 정리할 때마다"],
  ["Upstage 글자 읽기", "올린 사진. 사진 속 이름은 가릴 수 없어 그대로 가요. 사진은 저장하지 않아요", "사진으로 쓸 때만"],
  ["ElevenLabs(미국) 받아쓰기 · 읽어 주기", "녹음한 목소리, 읽어 줄 별지기 한마디. 이름은 가릴 수 없어 그대로 가요. 녹음은 받아쓴 뒤 바로 버려요", "말로 쓰거나 읽어 주기를 켤 때만"],
  ["Chroma Cloud(미국)", "가명 글로 만든 숫자 목록(벡터)과 id · 날짜 · 생각 종류. 글자는 보내지 않아요", "글을 정리할 때마다"],
  ["Vercel(미국 회사, 서버는 서울 지역)", "화면과 서버. 요청이 지나가고 원문 없는 실행 기록이 1시간 남아요", "쓸 때마다"],
  ["Supabase(서울)", "로그인과 DB. 원문은 사용자별 키로 암호화해 저장해요", "늘"],
  ["Google(미국)", "구글 로그인", "로그인할 때"],
];

function Check({ id, checked, onChange, children }: { id: string; checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <label htmlFor={id} className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap", color: "var(--text)", fontSize: "1rem" }}>
      <input id={id} type="checkbox" style={BOX} checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

export default function ConsentPage() {
  const [c, setC] = useState<Consent | null>(null);
  const [required, setRequired] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [age, setAge] = useState<"" | "14+" | "under">("");
  const [operator, setOperator] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = () => getConsent().then((x) => {
    setC(x);
    if (x.agreed && !x.needed) { setRequired(true); setSensitive(true); setAge("14+"); setOperator(x.agreed.operator_read); }
  }, (e) => setErr(why(e, "동의 내용을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.")));
  useEffect(() => { load(); }, []);

  if (err && !c) return <main><p className="err" role="alert">{err}</p></main>;
  if (!c) return <main><p className="sub">동의 내용을 불러오는 중…</p></main>;
  const again = !c.needed;   // 이미 지금 판에 동의함(선택 동의 바꾸기)
  const ok = required && sensitive && age === "14+";

  const submit = async () => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const r = await saveConsent({ version: c.version, required, sensitive, age14: age === "14+", operator_read: operator });
      if (again) { setC(r); setMsg("바꾼 내용을 저장했어요."); setBusy(false); }
      else window.location.assign("/");   // Shell 이 동의를 다시 확인하고 첫 화면(이야기하기)을 연다
    } catch (e) {
      setErr(why(e, "저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.")); setBusy(false);
      load();   // 문구 판이 바뀌었으면(409) 새 판을 다시 받는다
    }
  };

  return (
    <main>
      <h1>{again ? "동의 내용" : "나의 우주를 쓰기 전에"}</h1>
      <p className="sub">동의 문구 {c.version} 판{c.agreed && ` · 마지막으로 동의한 때 ${c.agreed.at.slice(0, 10)}`}</p>
      {!again && <p>나의 우주는 일기를 생각 단위로 나눠 우주로 보여 주고 별지기가 말을 거는 <b>시험 단계</b> 서비스예요.
        일기는 아주 사적인 글이라, 쓰기 전에 무엇이 어디로 가는지 알려 드리고 동의를 받아요.</p>}

      <section className="card stack" aria-label="외부로 나가는 곳">
        <h2>외부로 나가는 곳</h2>
        <p className="sub" style={{ margin: 0 }}>정리 · 말 걸기 요청(Upstage Studio · Solar)에는 사람 이름을 가명으로 바꿔 보내고, 보내기 직전에 실명이 남았는지 한 번 더 봐요.
          글자 읽기 · 받아쓰기 · 읽어 주기는 이름을 가릴 수 없어서 예외예요.</p>
        <ul style={UL}>
          {OUT.map(([who, what, when]) => <li key={who}><b>{who}</b>: {what} <span className="sub">({when})</span></li>)}
        </ul>
        <p className="sub" style={{ margin: 0 }}>미국에 있는 곳(Chroma Cloud · ElevenLabs · Vercel · Google)으로 가는 것은 국외 이전이에요. 자세한 내용(항목 · 나라 · 보관 기간 · 거부 방법)은 <Link href="/privacy">개인정보처리방침</Link> 5장.</p>
      </section>

      <section className="card stack" aria-label="일기 속 다른 사람">
        <h2>일기 속 다른 사람</h2>
        <p style={{ margin: 0 }}>일기에 나온 다른 사람의 이름 · 이야기도 저장돼요(이름은 암호화, 내 화면에만 실명). 기록을 내려받으면 다른 사람 이름도 실명 그대로 들어 있어요.
          다른 사람의 건강 · 비밀 같은 이야기는 꼭 필요한 만큼만 써 주세요. 사람 화면에서 한 사람을 지우면 글 속 그 이름이 관계 말(&quot;친구&quot; 같은)로 바뀌어요.</p>
      </section>

      <section className="card stack" aria-label="동의">
        <h2>동의</h2>
        <Check id="c-required" checked={required} onChange={setRequired}>
          <b>[필수]</b> <Link href="/terms">이용약관</Link>과 <Link href="/privacy">개인정보 수집 · 이용</Link>, 위의 외부 처리(국외 이전 포함)에 동의해요.
        </Check>
        <Check id="c-sensitive" checked={sensitive} onChange={setSensitive}>
          <b>[필수 · 따로]</b> 일기에 담길 수 있는 <b>민감정보</b>(건강 · 신앙 · 사상 · 성생활 같은 것)를 위 목적으로 처리하는 데 동의해요.
          <span className="sub"> 동의하지 않으면 일기를 정리할 수 없어 쓸 수 없어요.</span>
        </Check>
        <fieldset className="stack" aria-label="나이">
          <legend><b style={{ color: "var(--text)" }}>[필수]</b> 나이</legend>
          <div className="row">
            <button type="button" className="small" aria-pressed={age === "14+"} onClick={() => setAge("14+")}>만 14세 이상이에요</button>
            <button type="button" className="small" aria-pressed={age === "under"} onClick={() => setAge("under")}>만 14세 미만이에요</button>
          </div>
        </fieldset>
        {age === "under" && (
          <div className="care stack" role="alert" data-testid="under-14">
            <p style={{ margin: 0 }}>만 14세 미만은 법정대리인 동의 절차가 아직 없어 <b>지금은 쓸 수 없어요.</b> 아무것도 저장하지 않았어요.</p>
            {!MOCK && <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>}
          </div>
        )}
        <Check id="c-operator" checked={operator} onChange={setOperator}>
          <b>[선택]</b> 품질 개선을 위해 운영자가 내가 남긴 피드백(불편한 점 한 줄 · 아니에요 등)과 그 대상 문장을 읽을 수 있어요.
          <span className="sub"> 다른 사람 이름은 가명으로 보이고, 읽을 때마다 기록을 남겨요. 동의하지 않으면 숫자로만 모아요. 언제든 이 화면에서 거둘 수 있어요.</span>
        </Check>
        <button className="primary" disabled={!ok || busy} onClick={submit}>{busy ? "저장하는 중…" : again ? "바꾼 내용 저장" : "동의하고 시작하기"}</button>
        {msg && <p className="toast" role="status">{msg}</p>}
        {err && <p className="err" role="alert">{err}</p>}
      </section>

      <section className="card stack" aria-label="동의하지 않을 때">
        <p className="sub" style={{ margin: 0 }}>동의하지 않으면 기록을 쓸 수 없어요. {again ? "선택 동의는 끄고 저장하면 바로 거둬져요." : "이미 쓴 기록이 있으면 "}
          {!again && <><Link href="/settings">설정</Link> 맨 아래에서 계정과 모든 기록을 지울 수 있어요.</>}</p>
        {!MOCK && !again && <button onClick={() => supabase()?.auth.signOut()}>동의하지 않고 나가기(로그아웃)</button>}
        <p className="sub" style={{ margin: 0 }}>문의: <Contact /></p>
      </section>
    </main>
  );
}
