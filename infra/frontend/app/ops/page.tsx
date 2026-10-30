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
// 2026-10-19T23:02:55+09:00 → 10/19 23:02 (서버가 한국 시각으로 준다)
const when = (iso: string | null | undefined) => {
  const m = /^\d{4}-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso ?? "");
  return m ? `${+m[1]}/${+m[2]} ${m[3]}:${m[4]}` : iso ?? "—";
};
// 실행 단계 · 오류 코드는 사람 말로, 원래 코드는 옆에 흐리게(찾아볼 때 쓰게)
const STEP: Record<string, string> = {
  safety: "안전 확인", names: "이름 가리기", record: "생각 나누기", record_input: "기록 입력", record_agent: "기록 Agent(Studio)",
  record_clean: "기록 다듬기", ontology: "해 · 작은 별 놓기", group_stars: "작은 별 묶기", past: "지난 생각 찾기",
  observe: "관측 Agent(Studio)", rules: "관계 규칙", voice: "한마디", save: "저장", start: "시작", resume: "이어서 하기",
  confirm: "요약 확인", chat_turn: "대화 한 턴", chat_done: "대화 정리", talk_turn: "대화 한 턴", talk_draft: "대화 초안",
  stt: "말 받아쓰기", tts: "읽어 주기", suggest_axis: "축 제안", ops_summarize: "피드백 정리" };
const CODE: Record<string, string> = {
  studio_timeout: "Studio 시간 초과", studio_failed: "Studio 실패", llm_failed: "Solar 호출 실패", llm_error: "Solar 오류",
  ocr_failed: "사진 글자 읽기 실패", stt_failed: "받아쓰기 실패", speech_failed: "말 처리 실패", tts_failed: "읽어 주기 실패",
  summarize_failed: "정리 실패", vector_delete_failed: "벡터 지우기 실패", account_delete_failed: "계정 지우기 실패" };
function Name({ k, map }: { k: string | null | undefined; map: Record<string, string> }) {
  if (!k) return <>—</>;
  return map[k] ? <>{map[k]}<span className="code">{k}</span></> : <>{k}</>;
}
const names = (o: Record<string, number>, map: Record<string, string>) =>
  Object.entries(o).map(([k, v]) => `${map[k] ?? k} ${v}`).join(" · ");

function Stat({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <div className="ops-stat">
      <span className="l">{label}</span>
      <span className="v">{value}</span>
      {note && <span className="n">{note}</span>}
    </div>
  );
}

// 한눈에: 큰 숫자 하나 + '괜찮아요 / 살펴보기'(ok 가 undefined 면 판정 없이 숫자만)
function Glance({ label, value, ok, note }: { label: string; value: React.ReactNode; ok?: boolean; note?: string }) {
  return (
    <div className={ok === false ? "ops-tile warn" : "ops-tile"}>
      <span className="l">{label}</span>
      <b>{value}</b>
      {ok !== undefined && <span className="state">{ok ? "괜찮아요" : "살펴보기"}</span>}
      {note && <span className="n">{note}</span>}
    </div>
  );
}

function Card({ label, title, desc, full, children }: { label: string; title: React.ReactNode; desc: string; full?: boolean; children: React.ReactNode }) {
  return (
    <section className={full ? "card stack full" : "card stack"} aria-label={label}>
      <h2>{title}</h2>
      <p className="ops-desc">{desc}</p>
      {children}
    </section>
  );
}

function Table({ head, rows, label, num = [] }: { head: string[]; rows: React.ReactNode[][]; label: string; num?: number[] }) {
  if (!rows.length) return <p className="sub">아직 없어요.</p>;
  return (
    <div className="ops-table">
      <table aria-label={label}>
        <thead><tr>{head.map((h, j) => <th key={h} className={num.includes(j) ? "num" : undefined}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={num.includes(j) ? "num" : undefined}>{c}</td>)}</tr>)}</tbody>
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
  const worse = s.personal ? s.personal.links_yes.worse + s.personal.dislike.worse : null;
  const loop = s.personal_loop ? undoRate(s.personal_loop.dials) : null;
  return (
    <main className="wide ops">
      <div className="ops-head">
        <h1>운영</h1>
        <p className="sub">모든 사용자의 숫자 · 코드만 보여요(원문 없음). {when(s.generated_at)} 기준.</p>
      </div>

      <section className="ops-glance" aria-label="한눈에">
        <Glance label="예산 사용" value={pct(c.used_ratio)} ok={!c.warn && !c.over} note={`${usd(c.total_usd)} / $${c.budget_usd}`} />
        <Glance label="실패한 기록" value={s.failures.entries} ok={s.failures.entries === 0} note={names(s.failures.by_code, CODE) || "없음"} />
        <Glance label="점선 맞아요" value={pct(s.satisfaction.yes_ratio)} note={`맞아요 ${s.satisfaction.yes} · 아니에요 ${s.satisfaction.no}`} />
        <Glance label="다음 날 다시 씀" value={pct(s.satisfaction.next_day.ratio)} note={`${s.satisfaction.next_day.returned}/${s.satisfaction.next_day.pairs}일`} />
        {worse !== null && <Glance label="개인 지표 나빠진 사람" value={`${worse}명`} ok={worse === 0} note="자기 기준보다 15%p 넘게" />}
        {loop && <Glance label="자동 조정 되돌림" value={pct(loop.ratio)} ok={loop.ratio == null || loop.ratio < UNDO_WARN}
          note={`옮김 ${loop.moved} · 되돌림 ${loop.undone}`} />}
      </section>

      <div className="ops-grid">
        <h2 className="ops-group">모두에게 같은 것 · 전체 관리 <span className="sub">공통 틀(온톨로지 · Agent 설정 · 규칙)이 잘 도는지, 비용 · 실패 · 반응</span></h2>
        <Card label="추정 비용" desc="운영 서버에서 쓴 AI 호출 비용(추정). 개발 · 시험 호출(runs/cost_ledger.jsonl)과 Upstage 콘솔 청구는 따로 봐요."
          title={<>추정 비용 {c.over ? <span className="badge o">예산을 넘었어요</span> : c.warn && <span className="badge o">예산의 80%를 넘었어요</span>}</>}>
          <div className="ops-stats">
            <Stat label="운영 실행 합계" value={usd(c.total_usd)} note={`예산 $${c.budget_usd} 의 ${pct(c.used_ratio)}`} />
            <Stat label="이번 달" value={usd(c.month_usd)} />
            <Stat label="글 한 편 평균" value={usd(s.runs.per_entry.avg_usd)} note={`${s.runs.per_entry.avg_s ?? "—"}초`} />
          </div>
          <div role="meter" aria-label="예산 사용" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((c.used_ratio ?? 0) * 100)} className="ops-meter">
            <i style={{ width: `${Math.min(100, (c.used_ratio ?? 0) * 100)}%`, background: c.warn ? "var(--orange)" : "var(--violet)" }} />
          </div>
          <div className="ops-chips" aria-label="단계별 비용">
            {Object.entries(c.by_step).map(([k, v]) => <span key={k} className="badge">{STEP[k] ?? k} {usd(v)}</span>)}
          </div>
        </Card>

        <Card label="사용자 · 만족 · 지향" title="만족 · 지향" desc="사용자 반응과 다시 쓰는지. '가까워졌다는 느낌'은 묻지 않아요(2026-10-13 결정).">
          <div className="ops-stats">
            <Stat label="사용자" value={s.users.total} note={`최근 7일 ${s.users.active_7d}명 · 열람 동의 ${s.users.operator_read}명`} />
            <Stat label="점선 맞아요 비율" value={pct(s.satisfaction.yes_ratio)} note={`맞아요 ${s.satisfaction.yes} · 아니에요 ${s.satisfaction.no}`} />
            <Stat label="다음 날 다시 쓴 비율" value={day(s.satisfaction.next_day)} />
            <Stat label="여러 해에 대해 쓰기" value={s.direction.multi_sun.avg_suns ?? "—"}
              note={`최근 ${s.direction.multi_sun.window_days}일 평균 해 수 · 2개 이상 ${pct(s.direction.multi_sun.share_2plus)}`} />
          </div>
          <div className="ops-chips" aria-label="반응 수">
            {Object.entries(s.satisfaction.reactions).map(([k, v]) => <span key={k} className="badge">{k} {v}</span>)}
          </div>
          <Table label="설정 번호별 반응" head={["설정", "맞아요", "아니에요", "좋아요", "별로"]} num={[1, 2, 3, 4]}
            rows={Object.entries(s.satisfaction.by_config).map(([k, v]) => [k, v["맞아요"] ?? 0, v["아니에요"] ?? 0, v["좋아요"] ?? 0, v["별로"] ?? 0])} />
        </Card>

        <Card label="말 걸기" title="말 걸기 · 한마디" desc="별지기 한마디에 제안을 얼마나 넣고, 사용자가 어떻게 받았는지.">
          <div className="ops-stats">
            <Stat label="제안 넣은 한마디" value={pct(s.voice.suggested_ratio)} note={`한마디 ${s.voice.messages}개`} />
            <Stat label="한마디 반복(다시 만듦)" value={pct(s.voice.repeat_ratio)} />
            <Stat label="'별로' 비율" value={pct(s.voice.dislike_ratio)} />
            <Stat label="다음 날 다시 씀 · 제안 있음" value={day(s.voice.next_day_with_suggestion)} />
            <Stat label="다음 날 다시 씀 · 제안 없음" value={day(s.voice.next_day_without_suggestion)} />
          </div>
        </Card>

        <Card label="말 걸기 · 대화" title="대화" desc="이야기하기 대화가 끝까지 가는지, 어디서 그만두는지.">
          <div className="ops-stats">
            <Stat label="대화" value={s.talk.conversations} note={`평균 ${s.talk.avg_turns ?? "—"}턴 · 정리 ${s.talk.finished} · 그만둠 ${s.talk.dropped}`} />
            <Stat label="그만둔 지점(턴)" value={Object.entries(s.talk.drop_at).map(([k, v]) => `${k}턴 ${v}`).join(" · ") || "—"} />
            <Stat label="제안 직후 그만둠" value={pct(s.talk.stop_after_suggestion)} note={`제안 없는 턴 ${pct(s.talk.stop_without_suggestion)}`} />
            <Stat label="요약 확인에서 고친 비율" value={pct(s.talk.edited_ratio)} note={`확인 ${s.talk.confirms}번 중 고친 확인 ${pct(s.talk.confirms_with_edit)}`} />
          </div>
        </Card>

        <Card full label="관문 · 실패 · 평가" title="관문 · 실패 · 평가" desc="안전 관문이 막은 것, 실패한 기록, 정해 둔 목록 밖 값, 골든셋 시험 결과.">
          <div className="ops-stats">
            <Stat label="실명 관문이 막은 요청" value={s.gates.real_name_leak} />
            <Stat label="말 걸기 검사로 다시 만든 한마디" value={pct(s.gates.voice_regenerated_ratio)} note={`${s.gates.voice_regenerated}/${s.gates.voice_runs}`} />
            <Stat label="실패한 기록" value={s.failures.entries} note={names(s.failures.by_code, CODE)} />
            <Stat label="목록 밖 값(기타)" value={s.other_values.kind + s.other_values.certainty + s.other_values.value}
              note={`종류 ${s.other_values.kind} · 확신 ${s.other_values.certainty} · 가치 ${s.other_values.value} / 생각 ${s.other_values.thoughts}`} />
          </div>
          <div className="ops-two">
            <div className="stack">
              <h3>최근 실패</h3>
              <Table label="실패한 기록" head={["때", "기록", "단계", "코드"]}
                rows={s.failures.recent.map((f) => [when(f.at), f.entry_id, <Name key="s" k={f.step} map={STEP} />, <Name key="c" k={f.code} map={CODE} />])} />
            </div>
            <div className="stack">
              <h3>골든셋 결과</h3>
              {s.eval ? <Table label="골든셋" head={["파일", "관문", "통과", "회귀", "비용"]} num={[2, 3, 4]}
                rows={s.eval.map((e) => [e.file, e.gate_ok ? "통과" : "아님", `${e.passed}/${e.total}`, e.regressions, usd(e.est_usd)])} />
                : <p className="sub">배포 서버에는 골든셋 결과 파일이 없어요. 로컬에서 <code>uv run --frozen python eval/run.py</code> 결과(eval/results)를 봐요.</p>}
            </div>
          </div>
        </Card>

        <Card full label="실행 기록" title={<>실행 기록 <span className="sub">({s.runs.count}번)</span></>} desc="일기 한 편 · 대화 한 턴이 거친 단계마다 걸린 시간 · 호출 · 비용 · 오류.">
          <Table label="단계별" head={["단계", "횟수", "평균 시간", "실패", "비용"]} num={[1, 2, 3, 4]}
            rows={s.runs.by_step.map((r) => [<Name key="s" k={r.step} map={STEP} />, r.count, `${(r.avg_ms / 1000).toFixed(1)}초`, r.fails, usd(r.est_usd)])} />
          <h3>최근 실행</h3>
          <Table label="최근 실행" head={["때", "단계", "시간", "호출", "비용", "코드", "설정", "기록"]} num={[2, 3, 4]}
            rows={s.runs.recent.map((r) => [when(r.at), <Name key="s" k={r.step} map={STEP} />, r.ms == null ? "—" : `${(r.ms / 1000).toFixed(1)}초`, r.calls,
              usd(r.est_usd), r.code ? <Name key="c" k={r.code} map={CODE} /> : "", r.config ?? "", r.entry_id ?? ""])} />
        </Card>

        <h2 className="ops-group">사람마다 · 개인 맞춤 관리 <span className="sub">사람마다 반응으로 자동으로 도는 개인 고리 — 분포와 사람 수만</span></h2>
        {s.personal && (
          <Card full label="사람마다 · 개인 지표" title={<>사람마다 · 개인 지표 <span className="sub">(분포만, 사람별 값은 보지 않아요)</span></>}
            desc="사람마다 설정은 반응에 맞춰 자동으로 한 칸씩 바뀌고(되돌리기 가능), 여기서는 그 고리가 잘 도는지만 봐요. 반응이 5번 넘게 쌓인 사람만 세고, 나빠진 사람 = 최근 14일이 그 전보다 15%p 이상 나쁨.">
            <div className="ops-stats">
              <Stat label="AI 추정 선 맞아요 (중앙값)" value={pct(s.personal.links_yes.median)}
                note={`${s.personal.links_yes.users}명 · 자기 기준보다 나빠진 사람 ${s.personal.links_yes.worse}명`} />
              <Stat label="한마디 별로 (중앙값)" value={pct(s.personal.dislike.median)}
                note={`${s.personal.dislike.users}명 · 자기 기준보다 나빠진 사람 ${s.personal.dislike.worse}명`} />
              <Stat label="글 10편당 고친 수 (중앙값)" value={s.personal.fixes.median ?? "—"} note={`${s.personal.fixes.users}명 · 고침 · 옮김 · 합침 · 떼어 냄`} />
            </div>
          </Card>
        )}

        {s.personal_loop && <LoopCard l={s.personal_loop} />}

        <h2 className="ops-group">사용자 목소리 · 공통 틀을 고칠 재료 <span className="sub">동의한 사용자의 피드백 원문 · 여러 사람의 같은 고침 · 오답 모으기</span></h2>
        <FeedbackPanel counts={s.feedback_text} />
        <ScriptToken />
      </div>
    </main>
  );
}

const DIAL: Record<string, string> = { cross_links: "다른 영역과 이어진 선 보이기", suggestions: "다음 걸음 제안 빈도" };
const UNDO_WARN = 0.3;   // ponytail: 자동 조정의 30% 넘게 되돌리면 문턱(반응 3번)이 낮다고 본다. 파일럿 뒤 다시 정한다
const undoRate = (ds: { moved: number; undone: number }[]) => {
  const moved = ds.reduce((a, d) => a + d.moved, 0), undone = ds.reduce((a, d) => a + d.undone, 0);
  return { moved, undone, ratio: moved ? undone / moved : null };
};

// 개인 고리: 개인 층이 켜진 사람 수 + 다이얼마다 자동으로 옮긴 수 · 방향 · 되돌림(사람 id 없이)
function LoopCard({ l }: { l: NonNullable<OpsSummary["personal_loop"]> }) {
  return (
    <Card full label="개인 고리" title={<>개인 고리 · 자동으로 맞춘 것 <span className="sub">(사람 id 없이)</span></>}
      desc={`반응이 한쪽으로 ${l.min}번 이상(반대쪽의 두 배) 쌓이면 그 사람 설정이 한 칸 바뀌고 알림이 떠요. 되돌림이 많으면 문턱이 낮다는 뜻이고, 여러 사람이 같은 방향으로 옮기면 기본값(공통 틀)을 바꿀 후보예요.`}>
      <div className="ops-stats">
        <Stat label="설정이 자동으로 바뀐 사람" value={`${l.on.auto}명`} />
        <Stat label="'별로' 금지 목록이 있는 사람" value={`${l.on.disliked}명`} note="그 한마디는 그 사람에게 다시 안 씀" />
        <Stat label="'아니에요' 규칙이 있는 사람" value={`${l.on.rejected}명`} note="지운 연결은 다른 묶음 사이에서 다시 안 보임" />
        <Stat label="고침으로 고정한 사람" value={`${l.on.fixed}명`} note="고침 · 옮김 · 합침 · 떼어 냄" />
      </div>
      <Table label="다이얼별 자동 조정" head={["설정", "옮김", "사람", "되돌림", "어디로"]} num={[1, 2, 3]}
        rows={l.dials.map((d) => {
          const r = d.moved ? d.undone / d.moved : null;
          return [DIAL[d.setting] ?? d.setting, d.moved, `${d.users}명`,
            <span key="u" className={r != null && r >= UNDO_WARN ? "ops-warn" : undefined}>{d.undone} ({pct(r)})</span>,
            Object.entries(d.to).map(([k, v]) => `${k} ${v}`).join(" · ")];
        })} />
    </Card>
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
    <section className="card stack full" aria-label="피드백 원문">
      <h2>피드백 원문 <span className="sub">(운영자 열람에 동의한 사용자만)</span></h2>
      <p className="ops-desc">
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
            rows={fb.items.map((x) => [x.user, when(x.at), x.target, x.value, x.text ?? "", x.target_text ?? "", x.config ?? ""])} />
          <p className="sub" style={{ margin: 0 }}>동의 안 한 사용자: {Object.entries(fb.not_consented).map(([k, v]) => `${k} ${v}`).join(" · ") || "없음"}</p>
          <h3>공통 틀 후보 <span className="sub">(2명 이상이 같은 방향으로 고친 것 · 바꿀지는 사람이 정하고 가상 인물 · 골든셋으로 시험)</span></h3>
          <Table label="공통 틀 후보" head={["고친 것", "방향", "사람", "횟수", "자주 나온 낱말"]} num={[2, 3]}
            rows={(fb.framework_candidates ?? []).map((x) => [x.kind, x.what, `${x.users}명`, x.count, x.words.join(" · ") || "—"])} />
          <h3>목록 밖 값 새 후보 <span className="sub">(정하는 것은 사람)</span></h3>
          <Table label="새 값 후보" head={["칸", "원래 말", "횟수"]} num={[2]} rows={fb.other_candidates.map((x) => [x.field, x.original, x.count])} />
        </div>
      )}
      {dg && (
        <div className="stack" aria-label="피드백 정리 결과">
          <h3>정리 결과 <span className="sub">(제안일 뿐 · 승인은 사람, 비용 {usd(dg.est_usd)})</span></h3>
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
    <section className="card stack full" aria-label="오답 모으기">
      <h2>주 1회 오답 모으기</h2>
      <p className="ops-desc">
        <code>OPS_TOKEN=… uv run --frozen python scripts/collect_feedback.py --api &lt;백엔드 주소&gt;</code> → runs/wrong/날짜.jsonl
        (동의한 사용자의 아니에요 · 별로 · 불편한 점 한 줄, 가명).
      </p>
      <div className="row"><button className="small" onClick={copy}>스크립트용 토큰 복사</button>{msg && <span className="sub" role="status">{msg}</span>}</div>
    </section>
  );
}
