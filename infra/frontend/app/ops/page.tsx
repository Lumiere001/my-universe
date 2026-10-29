"use client";
// 운영 화면(WS22 — PRD §7 473 · §8.0 · §8.3 · §8.7). 메뉴에는 없다. 백엔드가 ADMIN_EMAILS(운영자 구글 계정)만 열어 준다(아니면 403).
// 위쪽 숫자는 모든 사용자의 숫자 · 코드뿐(원문 0건). 피드백 원문은 운영자 열람에 동의한 사용자 것만, 누를 때만 불러오고
// 그때마다 서버에 열람 기록이 남는다. '피드백 정리'는 누를 때만 Solar 를 한 번 부른다(유료, 비용은 위 합계에 들어감).
import { useState } from "react";
import { ApiError, getOpsFeedback, getOpsSummary, MOCK, summarizeFeedback, supabase,
  type NextDay, type OpsDigest, type OpsFeedback, type OpsSummary } from "@/lib/api";
import { useLoad } from "@/lib/use";

const pct = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);
const usd = (x: number | null | undefined) => (x == null ? "—" : `$${x.toFixed(x < 1 ? 4 : 2)}`);
const day = (d: NextDay) => `${pct(d.ratio)} (${d.returned}/${d.pairs})`;
const TABLE = { width: "100%", borderCollapse: "collapse", fontSize: ".85rem" } as const;
const CELL = { padding: "4px 6px", borderBottom: "1px solid var(--line)", textAlign: "left", whiteSpace: "nowrap" } as const;

function Stat({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <div style={{ minWidth: 140, flex: "1 1 140px" }}>
      <div className="sub">{label}</div>
      <div style={{ fontSize: "1.3rem", fontWeight: 700 }}>{value}</div>
      {note && <div className="sub" style={{ fontSize: ".78rem" }}>{note}</div>}
    </div>
  );
}

function Table({ head, rows, label }: { head: string[]; rows: React.ReactNode[][]; label: string }) {
  if (!rows.length) return <p className="sub">아직 없어요.</p>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={TABLE} aria-label={label}>
        <thead><tr>{head.map((h) => <th key={h} style={CELL}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} style={CELL}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export default function OpsPage() {
  const [s, err] = useLoad<OpsSummary>(getOpsSummary);
  if (err) {   // 운영자가 아니면 백엔드가 403 '운영자만 볼 수 있어요.'
    return (
      <main><div className="card stack" role="alert">
        <h1>운영</h1>
        <p>{err}</p>
        <p className="sub">운영자 계정은 백엔드 환경변수 ADMIN_EMAILS 로 정해요.</p>
      </div></main>
    );
  }
  if (!s) return <main><p className="sub">불러오는 중…</p></main>;
  const c = s.cost;
  return (
    <main className="wide">
      <h1>운영</h1>
      <p className="sub">모든 사용자의 숫자 · 코드만 보여요(원문 없음). {s.generated_at} 기준.</p>

      <section className="card stack" aria-label="추정 비용">
        <h2 style={{ margin: 0 }}>추정 비용 {c.over ? <span className="badge o">예산을 넘었어요</span> : c.warn && <span className="badge o">예산의 80%를 넘었어요</span>}</h2>
        <div className="row">
          <Stat label="운영 실행 합계" value={usd(c.total_usd)} note={`예산 $${c.budget_usd} 의 ${pct(c.used_ratio)}`} />
          <Stat label="이번 달" value={usd(c.month_usd)} />
          <Stat label="글 한 편 평균" value={usd(s.runs.per_entry.avg_usd)} note={`${s.runs.per_entry.avg_s ?? "—"}초`} />
        </div>
        <div role="meter" aria-label="예산 사용" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((c.used_ratio ?? 0) * 100)}
          style={{ height: 8, borderRadius: 4, background: "var(--panel2)", overflow: "hidden" }}>
          <div style={{ width: `${Math.min(100, (c.used_ratio ?? 0) * 100)}%`, height: "100%", background: c.warn ? "var(--orange)" : "var(--violet)" }} />
        </div>
        <p className="sub" style={{ margin: 0 }}>
          단계별: {Object.entries(c.by_step).map(([k, v]) => `${k} ${usd(v)}`).join(" · ") || "—"}.
          개발 · 시험 호출(runs/cost_ledger.jsonl)과 Upstage 콘솔 청구는 따로 봐요.
        </p>
      </section>

      <section className="card stack" aria-label="사용자 · 만족 · 지향">
        <h2 style={{ margin: 0 }}>만족 · 지향</h2>
        <div className="row">
          <Stat label="사용자" value={s.users.total} note={`최근 7일 ${s.users.active_7d}명 · 열람 동의 ${s.users.operator_read}명`} />
          <Stat label="점선 맞아요 비율" value={pct(s.satisfaction.yes_ratio)} note={`맞아요 ${s.satisfaction.yes} · 아니에요 ${s.satisfaction.no}`} />
          <Stat label="다음 날 다시 쓴 비율" value={day(s.satisfaction.next_day)} />
          <Stat label="여러 해에 대해 쓰기" value={s.direction.multi_sun.avg_suns ?? "—"}
            note={`최근 ${s.direction.multi_sun.window_days}일 평균 해 수 · 2개 이상 ${pct(s.direction.multi_sun.share_2plus)}`} />
        </div>
        <p className="sub" style={{ margin: 0 }}>
          반응: {Object.entries(s.satisfaction.reactions).map(([k, v]) => `${k} ${v}`).join(" · ")}.
          &apos;가까워졌다는 느낌&apos;은 묻지 않아요(2026-10-13 결정).
        </p>
        <Table label="설정 번호별 반응" head={["설정", "맞아요", "아니에요", "좋아요", "별로"]}
          rows={Object.entries(s.satisfaction.by_config).map(([k, v]) => [k, v["맞아요"] ?? 0, v["아니에요"] ?? 0, v["좋아요"] ?? 0, v["별로"] ?? 0])} />
      </section>

      {s.personal && (
        <section className="card stack" aria-label="사람마다 · 개인 지표">
          <h2 style={{ margin: 0 }}>사람마다 · 개인 지표 <span className="sub">(분포만, 사람별 값은 보지 않아요)</span></h2>
          <div className="row">
            <Stat label="AI 추정 선 맞아요 (중앙값)" value={pct(s.personal.links_yes.median)}
              note={`${s.personal.links_yes.users}명 · 자기 기준보다 나빠진 사람 ${s.personal.links_yes.worse}명`} />
            <Stat label="한마디 별로 (중앙값)" value={pct(s.personal.dislike.median)}
              note={`${s.personal.dislike.users}명 · 자기 기준보다 나빠진 사람 ${s.personal.dislike.worse}명`} />
            <Stat label="글 10편당 고친 수 (중앙값)" value={s.personal.fixes.median ?? "—"} note={`${s.personal.fixes.users}명 · 고침 · 옮김 · 합침`} />
          </div>
          <p className="sub" style={{ margin: 0 }}>
            반응이 5번 넘게 쌓인 사람만 셉니다. 나빠진 사람 = 최근 14일이 그 전보다 15%p 이상 나쁨. 사람마다 설정은 반응에 맞춰 자동으로 한 칸씩 바뀌고(되돌리기 가능), 여기서는 그 고리가 잘 도는지만 봅니다.
          </p>
        </section>
      )}

      <section className="card stack" aria-label="말 걸기 · 대화">
        <h2 style={{ margin: 0 }}>말 걸기 · 대화</h2>
        <div className="row">
          <Stat label="제안 넣은 한마디" value={pct(s.voice.suggested_ratio)} note={`한마디 ${s.voice.messages}개`} />
          <Stat label="한마디 반복(다시 만듦)" value={pct(s.voice.repeat_ratio)} />
          <Stat label="'별로' 비율" value={pct(s.voice.dislike_ratio)} />
          <Stat label="다음 날 다시 씀 · 제안 있음" value={day(s.voice.next_day_with_suggestion)} />
          <Stat label="다음 날 다시 씀 · 제안 없음" value={day(s.voice.next_day_without_suggestion)} />
        </div>
        <div className="row">
          <Stat label="대화" value={s.talk.conversations} note={`평균 ${s.talk.avg_turns ?? "—"}턴 · 정리 ${s.talk.finished} · 그만둠 ${s.talk.dropped}`} />
          <Stat label="그만둔 지점(턴)" value={Object.entries(s.talk.drop_at).map(([k, v]) => `${k}턴 ${v}`).join(" · ") || "—"} />
          <Stat label="제안 직후 그만둠" value={pct(s.talk.stop_after_suggestion)} note={`제안 없는 턴 ${pct(s.talk.stop_without_suggestion)}`} />
          <Stat label="요약 확인에서 고친 비율" value={pct(s.talk.edited_ratio)} note={`확인 ${s.talk.confirms}번 중 고친 확인 ${pct(s.talk.confirms_with_edit)}`} />
        </div>
      </section>

      <section className="card stack" aria-label="관문 · 실패 · 평가">
        <h2 style={{ margin: 0 }}>관문 · 실패 · 평가</h2>
        <div className="row">
          <Stat label="실명 관문이 막은 요청" value={s.gates.real_name_leak} />
          <Stat label="말 걸기 검사로 다시 만든 한마디" value={pct(s.gates.voice_regenerated_ratio)} note={`${s.gates.voice_regenerated}/${s.gates.voice_runs}`} />
          <Stat label="실패한 기록" value={s.failures.entries} note={Object.entries(s.failures.by_code).map(([k, v]) => `${k} ${v}`).join(" · ")} />
          <Stat label="목록 밖 값(기타)" value={s.other_values.kind + s.other_values.certainty + s.other_values.value}
            note={`종류 ${s.other_values.kind} · 확신 ${s.other_values.certainty} · 가치 ${s.other_values.value} / 생각 ${s.other_values.thoughts}`} />
        </div>
        <Table label="실패한 기록" head={["때", "기록", "단계", "코드"]} rows={s.failures.recent.map((f) => [f.at, f.entry_id, f.step, f.code])} />
        <h3 style={{ margin: 0 }}>골든셋 결과</h3>
        {s.eval ? <Table label="골든셋" head={["파일", "관문", "통과", "회귀", "비용"]}
          rows={s.eval.map((e) => [e.file, e.gate_ok ? "통과" : "아님", `${e.passed}/${e.total}`, e.regressions, usd(e.est_usd)])} />
          : <p className="sub">배포 서버에는 골든셋 결과 파일이 없어요. 로컬에서 <code>uv run --frozen python eval/run.py</code> 결과(eval/results)를 봐요.</p>}
      </section>

      <section className="card stack" aria-label="실행 기록">
        <h2 style={{ margin: 0 }}>실행 기록 <span className="sub">({s.runs.count}번)</span></h2>
        <Table label="단계별" head={["단계", "횟수", "평균 시간", "실패", "비용"]}
          rows={s.runs.by_step.map((r) => [r.step, r.count, `${(r.avg_ms / 1000).toFixed(1)}초`, r.fails, usd(r.est_usd)])} />
        <Table label="최근 실행" head={["때", "단계", "시간", "호출", "비용", "코드", "설정", "기록"]}
          rows={s.runs.recent.map((r) => [r.at, r.step, r.ms == null ? "—" : `${(r.ms / 1000).toFixed(1)}초`, r.calls, usd(r.est_usd), r.code ?? "", r.config ?? "", r.entry_id ?? ""])} />
      </section>

      <FeedbackPanel counts={s.feedback_text} />
      <ScriptToken />
    </main>
  );
}

// 피드백 원문(동의한 사용자만, 가명) · 목록 밖 값 후보 · 피드백 정리(Solar)
function FeedbackPanel({ counts }: { counts: OpsSummary["feedback_text"] }) {
  const [fb, setFb] = useState<OpsFeedback | null>(null);
  const [dg, setDg] = useState<OpsDigest | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const run = async <T,>(what: string, fn: () => Promise<T>, set: (v: T) => void) => {
    setBusy(what); setErr("");
    try { set(await fn()); } catch (e) { setErr(e instanceof ApiError && e.message ? e.message : "불러오지 못했어요."); }
    setBusy("");
  };
  return (
    <section className="card stack" aria-label="피드백 원문">
      <h2 style={{ margin: 0 }}>피드백 원문 <span className="sub">(운영자 열람에 동의한 사용자만)</span></h2>
      <p className="sub" style={{ margin: 0 }}>
        불편한 점 한 줄: 동의 {counts.consented}개 · 동의 안 함 {counts.not_consented}개(숫자만). 열어 볼 때마다 사용자별 열람 기록이 남고,
        다른 사람 이름은 가명으로 보여요.
      </p>
      <div className="row">
        <button onClick={() => run("fb", () => getOpsFeedback(30), setFb)} disabled={!!busy}>{busy === "fb" ? "여는 중…" : "최근 30일 열어 보기"}</button>
        <button onClick={() => run("dg", () => summarizeFeedback(30), setDg)} disabled={!!busy}>{busy === "dg" ? "정리하는 중…" : "피드백 정리(Solar 한 번)"}</button>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
      {fb && (
        <div className="stack">
          <Table label="피드백" head={["사용자", "때", "대상", "버튼", "남긴 말", "대상 문장", "설정"]}
            rows={fb.items.map((x) => [x.user, x.at.slice(0, 16), x.target, x.value, x.text ?? "", x.target_text ?? "", x.config ?? ""])} />
          <p className="sub" style={{ margin: 0 }}>동의 안 한 사용자: {Object.entries(fb.not_consented).map(([k, v]) => `${k} ${v}`).join(" · ") || "없음"}</p>
          <h3 style={{ margin: 0 }}>목록 밖 값 새 후보 <span className="sub">(정하는 것은 사람)</span></h3>
          <Table label="새 값 후보" head={["칸", "원래 말", "횟수"]} rows={fb.other_candidates.map((x) => [x.field, x.original, x.count])} />
        </div>
      )}
      {dg && (
        <div className="stack" aria-label="피드백 정리 결과">
          <h3 style={{ margin: 0 }}>정리 결과 <span className="sub">(제안일 뿐 · 승인은 사람, 비용 {usd(dg.est_usd)})</span></h3>
          {dg.groups.length ? dg.groups.map((g) => (
            <div key={g.reason} className="quote">
              <b>{g.reason}</b> {g.count}건 → {g.fix_where}<br />{g.suggestion}
              <div className="sub">{g.items.map((i) => dg.lines[i - 1]).filter(Boolean).join(" / ")}</div>
            </div>
          )) : <p className="sub">정리할 오답 재료가 없어요.</p>}
        </div>
      )}
    </section>
  );
}

// 주 1회 오답 모으기 스크립트(scripts/collect_feedback.py)에 쓸 토큰. 운영자 자신의 로그인 토큰(한 시간쯤 뒤 만료)
function ScriptToken() {
  const [msg, setMsg] = useState("");
  const copy = async () => {
    const t = MOCK ? "mock" : (await supabase()?.auth.getSession())?.data.session?.access_token;
    if (!t) { setMsg("로그인 토큰이 없어요."); return; }
    try { await navigator.clipboard.writeText(t); setMsg("복사했어요. 터미널에서 OPS_TOKEN 으로 붙여 넣으세요."); }
    catch { setMsg("복사하지 못했어요."); }
  };
  return (
    <section className="card stack" aria-label="오답 모으기">
      <h2 style={{ margin: 0 }}>주 1회 오답 모으기</h2>
      <p className="sub" style={{ margin: 0 }}>
        <code>OPS_TOKEN=… uv run --frozen python scripts/collect_feedback.py --api &lt;백엔드 주소&gt;</code> → runs/wrong/날짜.jsonl
        (동의한 사용자의 아니에요 · 별로 · 불편한 점 한 줄, 가명).
      </p>
      <div className="row"><button className="small" onClick={copy}>스크립트용 토큰 복사</button>{msg && <span className="sub" role="status">{msg}</span>}</div>
    </section>
  );
}
