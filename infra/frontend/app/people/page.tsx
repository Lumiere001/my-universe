"use client";
// (라) 사람 목록: 목록 + 고른 사람(넓은 화면은 옆에, 휴대폰은 목록 대신). 추가 · 고치기 · 지우기(이름을 forget_as 로 바꾸고 문장은 남김) · 얽힌 생각
import { useState } from "react";
import PersonThoughts from "@/components/PersonThoughts";
import { addPerson, deletePerson, deletePersonWithThoughts, listPeople, updatePerson, why, type Person } from "@/lib/api";
import { josa, particle } from "@/lib/josa";
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
      <div><label htmlFor={id + "n"}>이름</label><input id={id + "n"} value={f.name} maxLength={40} required onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div><label htmlFor={id + "k"}>부르는 말(별명)</label><input id={id + "k"} value={f.nickname} maxLength={40} onChange={(e) => setF({ ...f, nickname: e.target.value })} /></div>
      <div><label htmlFor={id + "r"}>나와의 관계</label><input id={id + "r"} value={f.relation} maxLength={20} required placeholder="예: 친구, 선배, 엄마" onChange={(e) => setF({ ...f, relation: e.target.value })} /></div>
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
  const [sel, setSel] = useState<string | null>(null);
  const [mode, setMode] = useState<"view" | "edit" | "del" | "add">("view");
  const [hide, setHide] = useState(false);   // 지울 때 그 사람이 나온 생각도 지우기(WS16)
  const [msg, setMsg] = useState("");
  const p = data?.people.find((x) => x.id === sel) ?? null;
  const open = mode === "add" || !!p;
  const pick = (id: string | null) => { setSel(id); setMode("view"); setMsg(""); setDelErr(""); setHide(false); };
  const forgetAs = (x: Person) => x.forget_as || "그 사람";

  return (
    <main className="ppl-page">
      <h1>사람 목록</h1>
      <p className="sub">일기에 나온 사람과, 그 사람과 얽힌 내 생각을 모아 봐요.</p>
      {err && <p className="err" role="alert">{err}</p>}
      {!data && !err && <p className="sub">사람 목록을 불러오는 중…</p>}
      {msg && <p className="toast" role="status">{msg}</p>}

      {data && (
        <div className="ppl" data-open={open ? "" : undefined}>
          <section className="ppl-list" aria-label="사람">
            {data.people.length === 0 && <p className="sub">아직 일기에 나온 사람이 없어요. 글에 이름이 나오면 여기에 저절로 올라와요.</p>}
            <ul>
              {data.people.map((x) => (
                <li key={x.id}>
                  <button className="file" aria-pressed={sel === x.id} onClick={() => pick(x.id)}>
                    <b>{x.name}</b><span className="meta">{x.relation || "관계 미정"} · 기록 {x.planets.length}편</span>
                  </button>
                </li>
              ))}
            </ul>
            <button className="small" onClick={() => { pick(null); setMode("add"); }}>사람 추가하기</button>
            <p className="sub ppl-aux">외부 AI로 보낼 때는 이 목록으로 이름을 가려요. 새 이름은 저절로 올라오고, 헷갈릴 때만 물어봐요.</p>
          </section>

          <div className="ppl-detail">
            {open && <button className="small ppl-back" onClick={() => pick(null)}>사람 목록으로</button>}
            {mode === "add" ? (
              <PersonForm init={EMPTY} label="사람 추가" onCancel={() => setMode("view")}
                onSave={async (f) => { const n = await addPerson(f); reload(); pick(n.id); setMsg(`${josa(f.name, "을/를")} 추가했어요.`); }} />
            ) : !p ? (
              <p className="sub">사람을 고르면 그 사람과 얽힌 생각이 여기에 보여요.</p>
            ) : (
              <section className="stack" aria-label={p.name}>
                {mode === "edit" ? (
                  <PersonForm init={p} label="고친 내용 저장" onCancel={() => setMode("view")}
                    onSave={async (f) => { await updatePerson(p.id, f); setMode("view"); setMsg(`${josa(f.name, "을/를")} 고쳤어요.`); reload(); }} />
                ) : mode === "del" ? (
                  <div className="stack" role="alertdialog" aria-label={`${p.name} 지우기 확인`}>
                    <p style={{ margin: 0 }}>
                      <b>{p.name}</b>{particle(p.name, "을/를")} 지우면, 저장된 글 속 “{p.name}”{particle(p.name, "을/를")} “{forgetAs(p)}”{particle(forgetAs(p), "으로/로")} 바꿔요.
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
                          const as = forgetAs(p);
                          pick(null);
                          setMsg(`${josa(p.name, "을/를")} 지웠어요. 글 ${r.replaced}곳의 이름을 “${as}”${particle(as, "으로/로")} 바꿨어요.${r.hidden ? ` 생각 ${r.hidden}개를 지웠어요.` : ""}`); reload();
                        } catch (e) { setDelErr(why(e, "지우지 못했어요. 그대로예요. 잠시 뒤 다시 해 주세요.")); }
                      }}>지우기</button>
                      <button className="small" onClick={() => { setMode("view"); setDelErr(""); }}>취소</button>
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
                      <button className="small" onClick={() => { setMode("edit"); setMsg(""); }} aria-label={`${p.name} 고치기`}>고치기</button>
                      <button className="small danger" onClick={() => { setMode("del"); setMsg(""); setDelErr(""); }} aria-label={`${p.name} 지우기`}>지우기</button>
                    </div>
                  </div>
                  <h2 className="ppl-h">얽힌 생각</h2>
                  <PersonThoughts id={p.id} />
                </>)}
              </section>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
