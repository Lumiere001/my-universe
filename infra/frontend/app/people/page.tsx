"use client";
// (라) 사람 목록: 추가 · 고치기 · 지우기(이름을 관계 말로 바꾸고 문장은 남김) · 얽힌 생각 펼치기
import { useState } from "react";
import PersonThoughts from "@/components/PersonThoughts";
import { addPerson, deletePerson, deletePersonWithThoughts, listPeople, updatePerson, why, type Person } from "@/lib/api";
import { useLoad } from "@/lib/use";

type Form = { name: string; nickname: string; relation: string };
const EMPTY: Form = { name: "", nickname: "", relation: "" };

function PersonForm({ init, label, onSave, onCancel }: { init: Form; label: string; onSave: (f: Form) => Promise<void>; onCancel?: () => void }) {
  const [f, setF] = useState(init);
  const [err, setErr] = useState("");
  const id = label.replace(/\s/g, "");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!f.name.trim() || !f.relation.trim()) return;
    setErr("");
    try { await onSave({ name: f.name.trim(), nickname: f.nickname.trim(), relation: f.relation.trim() }); }
    catch (x) { setErr(why(x, "저장하지 못했어요. 잠시 뒤 다시 해 주세요.")); }
  };
  return (
    <form className="stack" aria-label={label} onSubmit={submit}>
      <div className="row">
        <div style={{ flex: "1 1 140px" }}><label htmlFor={id + "n"}>이름</label><input id={id + "n"} value={f.name} maxLength={40} required onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
        <div style={{ flex: "1 1 140px" }}><label htmlFor={id + "k"}>부르는 말(별명)</label><input id={id + "k"} value={f.nickname} maxLength={40} onChange={(e) => setF({ ...f, nickname: e.target.value })} /></div>
        <div style={{ flex: "1 1 140px" }}><label htmlFor={id + "r"}>나와의 관계</label><input id={id + "r"} value={f.relation} maxLength={20} required placeholder="예: 친구, 선배, 엄마" onChange={(e) => setF({ ...f, relation: e.target.value })} /></div>
      </div>
      <div className="row">
        <button type="submit" className="primary small">{label}</button>
        {onCancel && <button type="button" className="small" onClick={onCancel}>취소</button>}
      </div>
      {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
    </form>
  );
}

export default function PeoplePage() {
  const [data, err, reload] = useLoad(listPeople, "사람 목록을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const [delErr, setDelErr] = useState("");
  const [edit, setEdit] = useState<string | null>(null);
  const [del, setDel] = useState<Person | null>(null);
  const [hide, setHide] = useState(false);   // 지울 때 그 사람이 나온 생각도 지우기(WS16)
  const [msg, setMsg] = useState("");
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  return (
    <main>
      <h1>사람 목록</h1>
      <p className="sub">일기에 나온 사람과, 그 사람과 얽힌 내 생각을 모아 봐요.</p>
      <p className="sub" style={{ fontSize: ".85rem" }}>외부 AI로 보낼 때는 이 목록으로 이름을 가려요. 새 이름은 저절로 올라오고, 헷갈릴 때만 물어봐요.</p>
      {err && <p className="err" role="alert">{err}</p>}
      {!data && !err && <p className="sub">사람 목록을 불러오는 중…</p>}
      {data?.people.length === 0 && <p className="sub">아직 일기에 나온 사람이 없어요. 글에 이름이 나오면 여기에 저절로 올라와요.</p>}
      {msg && <p className="toast" role="status">{msg}</p>}

      {data?.people.map((p) => (
        <section key={p.id} className="card" aria-label={p.name}>
          {edit === p.id ? (
            <PersonForm init={p} label="고친 내용 저장" onCancel={() => setEdit(null)}
              onSave={async (f) => { await updatePerson(p.id, f); setEdit(null); setMsg(`${f.name}을(를) 고쳤어요.`); reload(); }} />
          ) : del?.id === p.id ? (
            <div className="stack" role="alertdialog" aria-label={`${p.name} 지우기 확인`}>
              <p style={{ margin: 0 }}>
                <b>{p.name}</b>을(를) 지우면, 저장된 글에서 이름 “{p.name}”을(를) 관계 말 “{p.relation || "그 사람"}”(으)로 바꿔요.
                {hide ? " 그 사람이 나온 생각과 그 생각의 이어진 선은 우주에서 지워요(글 본문은 남아요)." : " 문장 · 생각 · 이어진 선은 그대로 남아요."}
              </p>
              <label className="row" style={{ gap: 6 }}>
                <input type="checkbox" checked={hide} onChange={(e) => setHide(e.target.checked)} style={{ width: "auto" }} />
                그 사람이 나온 생각도 지우기
              </label>
              <div className="row">
                <button className="danger small" onClick={async () => {
                  setDelErr("");
                  try {
                    // WS16: 고르면 그 사람이 나온 생각 · 관계 · 벡터도 지운다
                    const r = hide ? await deletePersonWithThoughts(p.id) : { ...(await deletePerson(p.id)), hidden: 0 };
                    setDel(null); setHide(false);
                    setMsg(`${p.name}을(를) 지웠어요. 글 ${r.replaced}곳의 이름을 “${p.relation || "그 사람"}”(으)로 바꿨어요.${r.hidden ? ` 생각 ${r.hidden}개를 지웠어요.` : ""}`); reload();
                  } catch (e) { setDelErr(why(e, "지우지 못했어요. 그대로예요. 잠시 뒤 다시 해 주세요.")); }
                }}>지우기</button>
                <button className="small" onClick={() => { setDel(null); setDelErr(""); }}>취소</button>
              </div>
              {delErr && <p className="err" role="alert" style={{ margin: 0 }}>{delErr}</p>}
            </div>
          ) : (<>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <b>{p.name}</b>{p.nickname && <span className="sub"> · {p.nickname}</span>} {p.relation ? <span className="badge">{p.relation}</span> : <span className="sub">관계 미정</span>}
                {p.auto && <span className="sub"> · 글에서 저절로 찾음</span>}
                <div className="sub">나온 기록 {p.planets.length}편</div>
              </div>
              <div className="row">
                <button className="small" aria-expanded={open === p.id} onClick={() => setOpen(open === p.id ? null : p.id)}
                  aria-label={`${p.name}과(와) 얽힌 생각`}>얽힌 생각 보기</button>
                <button className="small" onClick={() => { setEdit(p.id); setMsg(""); }} aria-label={`${p.name} 고치기`}>고치기</button>
                <button className="small danger" onClick={() => { setDel(p); setMsg(""); setDelErr(""); }} aria-label={`${p.name} 지우기`}>지우기</button>
              </div>
            </div>
            {open === p.id && <PersonThoughts id={p.id} />}
          </>)}
        </section>
      ))}

      <section className="card">
        {adding ? (
          <PersonForm init={EMPTY} label="사람 추가" onCancel={() => setAdding(false)}
            onSave={async (f) => { await addPerson(f); setAdding(false); setMsg(`${f.name}을(를) 추가했어요.`); reload(); }} />
        ) : <button onClick={() => setAdding(true)}>사람 추가하기</button>}
      </section>
    </main>
  );
}
