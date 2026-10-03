"""
universe_view.py

2D 우주 화면 (PRD §7). 글 = 별, 주제 = 성운, 관계 = 별자리.
Streamlit components.html 로 띄우는 독립 HTML(SVG + JS)을 만든다. 실명은 가린 뒤 넘긴다.

기호 규칙
- 색은 두 뜻: 보라 = 생각과 이어지는 관계(이어짐 · 바뀜 · 해소), 주황 = 충돌(긴장 · 어긋남 · 목표 충돌)
- 실선 = 원문으로 확인(작성자가 직접 씀), 점선 = AI 추정
- 별 크기 = 생각 수, 밝기 = 확신 정도, 빈 고리 = 다짐(지켜지면 채움), "?" = 질문
"""

import json

import gates

BRIGHT = {"단정": 1.0, "고민 중": 0.62, "질문": 0.5}


def _payload(state, selected=None):
    names = state["names"]
    mk = lambda s: gates.mask(s or "", names)
    th = state["thoughts"]
    hub_ids = list(state["hubs"])
    hubs, stars, cards = [], [], {}
    kept_vows = {r["from"] for r in state["relations"] if r["type"] == "이어짐" and th[r["from"]]["kind"] == "다짐"}
    inner = {r["from_record"] for r in state["relations"] if r["from_record"] == r["to_record"] and r["type"] == "긴장"}

    from universe import hub_xy
    for i, hid in enumerate(hub_ids):
        h = state["hubs"][hid]
        count = len({t["record_id"] for t in th.values() if t["hub"] == hid})
        x, y = hub_xy(i)
        topics = sorted((h.get("topics") or {}).items(), key=lambda kv: -kv[1])
        hubs.append({"id": hid, "name": h["name"], "x": x, "y": y, "count": count,
                     "topics": [{"name": mk(n), "count": c} for n, c in topics]})

    for rid in state["order"]:
        rec = state["records"][rid]
        if rid not in state["layout"]:
            continue
        mine = [th[t] for t in rec["thought_ids"] if t in th]
        links = {}
        for t in mine:
            links.setdefault(t["hub"], {"hub": t["hub"], "n": 0, "values": []})
            links[t["hub"]]["n"] += 1
            links[t["hub"]]["values"].append(t["value"])
        bright = sum(BRIGHT.get(t["certainty"], 0.6) for t in mine) / len(mine) if mine else 0.35
        vows = [t for t in mine if t["kind"] == "다짐"]
        x, y = state["layout"][rid]
        stars.append({
            "id": rid, "x": x, "y": y, "day": rec["day"], "title": mk(rec["title"]), "n": len(mine),
            "bright": round(bright, 2), "vow": ("kept" if any(v["id"] in kept_vows for v in vows) else "open") if vows else "",
            "question": any(t["kind"] == "질문" for t in mine), "links": list(links.values()),
            "near_hub": rec.get("near_hub"), "inner_tension": rid in inner,
        })
        rep = state["reports"].get(rid, {})
        cards[rid] = {
            "title": mk(rec["title"]), "day": rec["day"], "basis": rec["day_basis"], "type": rec.get("type", ""),
            "state": rep.get("observation_state", ""), "summary": mk(rep.get("summary") or rec.get("summary", "")),
            "question": mk(rep.get("question", "")),
            "meta": {k: [mk(x) for x in v] for k, v in rec.get("meta", {}).items() if v},
            "thoughts": [{"kind": t["kind"], "certainty": t["certainty"], "value": t["value"], "topic": t["topic"],
                          "thought": mk(t["thought"]), "quote": mk(t["quote"]), "change": mk(t["self_change"])} for t in mine],
        }
    rels = [{"id": r["id"], "type": r["type"], "a": r["from_record"], "b": r["to_record"], "line": r["line"],
             "topic": r["topic"], "why": mk(r["explanation"]), "axis": r["axis"],
             "aday": th[r["from"]]["day"], "bday": th[r["to"]]["day"]}
            for r in state["relations"] if r["status"] != "rejected" and r["from_record"] != r["to_record"]]
    return {"hubs": hubs, "stars": stars, "rels": rels, "cards": cards, "selected": selected}


def render(state, selected=None, height=660):
    data = json.dumps(_payload(state, selected), ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", data).replace("__H__", str(height))


TEMPLATE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>
:root{--bg:#070b19;--panel:#0f1530;--line:#232b52;--ink:#e8ebff;--mute:#9aa3c7;--violet:#a78bfa;--coral:#fb8a6b;--gold:#fcd679}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR",system-ui,sans-serif}
#wrap{position:relative;height:__H__px;border:1px solid var(--line);border-radius:14px;overflow:hidden}
#sky{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#111a3d 0%,#070b19 70%)}
svg{width:100%;height:100%;cursor:grab}svg:active{cursor:grabbing}
#card{position:absolute;right:10px;top:10px;bottom:10px;width:330px;background:#0f1530f2;border:1px solid var(--line);border-radius:12px;overflow:auto;padding:16px 16px 24px;font-size:13px;line-height:1.55;display:none;box-shadow:0 8px 30px #0008}
#card .x{position:absolute;right:10px;top:8px;cursor:pointer;color:var(--mute);font-size:18px}
#card h3{margin:0 0 4px;font-size:16px}#card .sub{color:var(--mute);font-size:12px;margin-bottom:10px}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;margin-right:4px;border:1px solid var(--line);color:var(--mute)}
.badge.v{color:var(--violet);border-color:#4c3f86}.badge.c{color:var(--coral);border-color:#7a3b2e}
.th{border-top:1px solid var(--line);padding:9px 0}.q{color:var(--mute);font-style:italic;margin-top:3px}
.rel{border-left:3px solid var(--violet);padding:4px 8px;margin:6px 0;background:#141b3c;border-radius:0 8px 8px 0}
.rel.c{border-left-color:var(--coral)}
#bar{position:absolute;left:12px;top:10px;display:flex;gap:6px}
#bar button{background:#141b3c;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:5px 10px;font-size:12px;cursor:pointer}
#bar button.on{border-color:var(--violet);color:var(--violet)}
#legend{position:absolute;left:12px;bottom:10px;font-size:11px;color:var(--mute);background:#0b1026cc;border:1px solid var(--line);border-radius:10px;padding:7px 10px;line-height:1.7}
#legend i{display:inline-block;width:22px;height:0;border-top:2px solid;vertical-align:middle;margin-right:5px}
#tip{position:absolute;pointer-events:none;background:#0b1026ee;border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:12px;display:none}
.hint{color:var(--mute)}
</style></head><body>
<div id="wrap"><div id="sky"><svg id="svg"></svg>
<div id="bar"><button data-m="base" class="on">기본</button><button data-m="value">가치 보기</button><button id="fit">전체 보기</button></div>
<div id="legend"><div><i style="border-color:var(--violet)"></i>이어짐 · 바뀜(화살표) · 해소</div>
<div><i style="border-color:var(--coral)"></i>긴장(쌍성) · 어긋남 · 목표 충돌</div>
<div><i style="border-color:#cfd3ef"></i>실선 = 원문으로 확인 &nbsp; <i style="border-color:#cfd3ef;border-top-style:dashed"></i>점선 = AI 추정</div>
<div>별 크기 = 생각 수 · 밝기 = 확신 · <span style="color:var(--gold)">◯</span> 다짐 · <span style="color:#c4b5fd">?</span> 질문</div></div>
<div id="tip"></div></div>
<div id="card"></div><div id="hint" style="position:absolute;right:14px;top:12px;font-size:12px;color:#9aa3c7">별을 누르면 그 글의 카드가 열립니다</div></div>
<script>
const D=__DATA__, NS="http://www.w3.org/2000/svg", svg=document.getElementById("svg");
const VAL={"자율":"#7dd3fc","도전":"#f472b6","즐거움":"#fde047","성취":"#fb923c","영향력":"#c084fc","안정":"#94a3b8","규범":"#a3e635","전통·신앙":"#fcd34d","배려":"#5eead4","공익":"#60a5fa"};
const CONF=new Set(["긴장","어긋남","목표 충돌"]);
let mode="base", sel=D.selected, view;
const S=Object.fromEntries(D.stars.map(s=>[s.id,s])), H=Object.fromEntries(D.hubs.map(h=>[h.id,h]));
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);(p||svg).appendChild(e);return e}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function fit(){const xs=[...D.stars.map(s=>s.x),...D.hubs.map(h=>h.x)],ys=[...D.stars.map(s=>s.y),...D.hubs.map(h=>h.y)];
 if(!xs.length){view=[-300,-220,600,440];return}
 const x0=Math.min(...xs)-110,x1=Math.max(...xs)+110,y0=Math.min(...ys)-90,y1=Math.max(...ys)+90;view=[x0,y0,x1-x0,y1-y0]}
function draw(){svg.innerHTML="";svg.setAttribute("viewBox",view.join(" "));
 const defs=el("defs",{});
 defs.innerHTML='<filter id="glow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
 +'<radialGradient id="neb"><stop offset="0" stop-color="#7c6cf0" stop-opacity=".34"/><stop offset=".55" stop-color="#4b3fa8" stop-opacity=".12"/><stop offset="1" stop-color="#1a1f4a" stop-opacity="0"/></radialGradient>'
 +'<marker id="arV" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#a78bfa"/></marker>';
 // 배경 별가루
 for(let i=0;i<140;i++){const r=(i*9301+49297)%233280/233280,q=(i*4241+1777)%233280/233280;
  el("circle",{cx:view[0]+r*view[2],cy:view[1]+q*view[3],r:.6+((i*7)%3)*.25,fill:"#fff",opacity:.12+((i*13)%5)*.05})}
 // 성운
 for(const h of D.hubs){const R=48+16*Math.sqrt(h.count);el("circle",{cx:h.x,cy:h.y,r:R,fill:"url(#neb)"});
  const t=el("text",{x:h.x,y:h.y+4,"text-anchor":"middle","font-size":13,"font-weight":700,fill:"#d9dcff",opacity:.92});t.textContent=h.name;
  const c=el("text",{x:h.x,y:h.y+19,"text-anchor":"middle","font-size":10,fill:"#9aa3c7"});c.textContent=h.count?h.count+"편":"아직 관측 안 됨";
  const tp=(h.topics||[]).slice(0,3).map(t=>t.name).join(" · ");if(tp){const u=el("text",{x:h.x,y:h.y+32,"text-anchor":"middle","font-size":9,fill:"#7f88b0"});u.textContent=tp}}
 const on=sel?new Set([sel,...D.rels.filter(r=>r.a===sel||r.b===sel).flatMap(r=>[r.a,r.b])]):null;
 // 글 → 주제 선 (생각이 올라가는 선)
 for(const s of D.stars){const dim=on&&!on.has(s.id)?.18:1;
  if(!s.links.length&&s.near_hub&&H[s.near_hub]){const h=H[s.near_hub];el("line",{x1:s.x,y1:s.y,x2:h.x,y2:h.y,stroke:"#8a90b8","stroke-width":.7,opacity:.22*dim})}
  for(const l of s.links){const h=H[l.hub];if(!h)continue;
   let col=s.inner_tension?"#fb8a6b":"#9d8cf5";
   if(mode==="value"){const v=l.values.find(v=>VAL[v]);col=v?VAL[v]:"#8a90b8"}
   el("line",{x1:s.x,y1:s.y,x2:h.x,y2:h.y,stroke:col,"stroke-width":.8+l.n*.7,opacity:.38*dim})}}
 // 별자리 (관계)
 for(const r of D.rels){const a=S[r.a],b=S[r.b];if(!a||!b)continue;const c=CONF.has(r.type);
  const dim=on&&!(r.a===sel||r.b===sel)?.15:1, col=c?"#fb8a6b":"#a78bfa", dash=r.line==="점선"?"5 4":"";
  if(r.type==="긴장"){const mx=(a.x+b.x)/2,my=(a.y+b.y)/2,dx=b.x-a.x,dy=b.y-a.y,k=.28;
   for(const sg of [1,-1])el("path",{d:`M${a.x},${a.y} Q${mx-dy*k*sg},${my+dx*k*sg} ${b.x},${b.y}`,fill:"none",stroke:col,"stroke-width":1.6,"stroke-dasharray":dash,opacity:.9*dim})}
  else{const ln=el("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:col,"stroke-width":r.type==="이어짐"?1.3:1.8,"stroke-dasharray":dash,opacity:.92*dim});
   if(r.type==="바뀜"||r.type==="해소"){const L=Math.hypot(b.x-a.x,b.y-a.y)||1,pad=7+ (b.n||0)*1.8;
    ln.setAttribute("x2",b.x-(b.x-a.x)/L*pad);ln.setAttribute("y2",b.y-(b.y-a.y)/L*pad);ln.setAttribute("marker-end","url(#arV)")}
   if(r.type==="해소")el("circle",{cx:b.x,cy:b.y,r:9+(b.n||0)*1.8,fill:"none",stroke:"#a78bfa","stroke-width":1,opacity:.7*dim,"stroke-dasharray":dash})}
  const hit=el("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:"transparent","stroke-width":10});
  hit.addEventListener("mousemove",e=>tip(e,`<b>${r.type}</b> · ${r.line} · ${esc(r.topic)}<br>${r.aday} → ${r.bday}<br><span class=hint>${esc(r.why)}</span>${r.axis?`<br>축: ${esc(r.axis)}`:""}`));
  hit.addEventListener("mouseleave",()=>tipOff())}
 // 별
 for(const s of D.stars){const R=Math.min(3.6+s.n*1.7,13),dim=on&&!on.has(s.id)?.25:1,g=el("g",{style:"cursor:pointer"});
  if(s.vow)el("circle",{cx:s.x,cy:s.y,r:R+4.5,fill:s.vow==="kept"?"#fcd67933":"none",stroke:"#fcd679","stroke-width":s.vow==="kept"?2:1.1,opacity:.9*dim},g);
  el("circle",{cx:s.x,cy:s.y,r:R,fill:"#fff",opacity:(.25+.75*s.bright)*dim,filter:"url(#glow)"},g);
  if(s.id===sel)el("circle",{cx:s.x,cy:s.y,r:R+9,fill:"none",stroke:"#fff","stroke-width":1,opacity:.8},g);
  if(s.question){const t=el("text",{x:s.x+R+3,y:s.y-R-1,"font-size":10,"font-weight":700,fill:"#c4b5fd",opacity:dim},g);t.textContent="?"}
  g.addEventListener("click",e=>{e.stopPropagation();sel=s.id;draw();card(s.id)});
  g.addEventListener("mousemove",e=>tip(e,`${s.day} · ${esc(s.title)}<br><span class=hint>생각 ${s.n}개</span>`));
  g.addEventListener("mouseleave",()=>tipOff())}}
function tip(e,h){const t=document.getElementById("tip"),r=document.getElementById("sky").getBoundingClientRect();
 t.innerHTML=h;t.style.display="block";t.style.left=(e.clientX-r.left+12)+"px";t.style.top=(e.clientY-r.top+12)+"px"}
function tipOff(){document.getElementById("tip").style.display="none"}
function card(id){const c=D.cards[id],box=document.getElementById("card"),hint=document.getElementById("hint");if(!c){box.style.display="none";hint.style.display="block";return}box.style.display="block";hint.style.display="none";
 const rels=D.rels.filter(r=>r.a===id||r.b===id);
 let h=`<span class=x onclick="sel=null;draw();card(null)">✕</span><h3>${esc(c.title)}</h3><div class=sub>${c.day} (${c.basis}) · ${esc(c.type)}${c.state?" · 관측: "+esc(c.state):""}</div>`;
 if(c.summary)h+=`<div>${esc(c.summary)}</div>`;
 if(c.question)h+=`<div style="margin:8px 0;color:#c4b5fd">다음에 써 볼 질문 · ${esc(c.question)}</div>`;
 h+=`<div style="margin-top:10px;font-weight:700">선 위의 생각 ${c.thoughts.length}개</div>`;
 if(!c.thoughts.length)h+=`<div class=hint>생각이 없는 글이라 가까운 성운에 희미하게만 이어 두었습니다.</div>`;
 for(const t of c.thoughts)h+=`<div class=th><span class="badge v">${esc(t.kind)}</span><span class=badge>${esc(t.certainty)}</span><span class=badge>${esc(t.topic)}</span>${t.value?`<span class=badge>${esc(t.value)}</span>`:""}
  <div style="margin-top:4px">${esc(t.thought)}</div><div class=q>“${esc(t.quote)}”</div>${t.change?`<div style="color:var(--violet);margin-top:3px">스스로 쓴 변화: ${esc(t.change)}</div>`:""}</div>`;
 if(rels.length){h+=`<div style="margin-top:12px;font-weight:700">이 별의 별자리 ${rels.length}개</div>`;
  for(const r of rels){const other=r.a===id?r.bday:r.aday;h+=`<div class="rel ${CONF.has(r.type)?"c":""}"><b>${r.type}</b> · ${r.line} · ${esc(r.topic)} · ${r.a===id?"→ ":"← "}${other}<div class=hint>${esc(r.why)}</div>${r.axis?`<div class=hint>축: ${esc(r.axis)}</div>`:""}</div>`}}
 const m=c.meta||{},lab={triggers:"계기",addressee:"말 거는 대상",roles:"등장 관계",references:"참고한 것",period:"다루는 기간"};
 const mm=Object.keys(lab).filter(k=>m[k]&&m[k].length).map(k=>`${lab[k]}: ${m[k].map(esc).join(", ")}`);
 if(mm.length)h+=`<div class=hint style="margin-top:12px">${mm.join("<br>")}</div>`;
 h+=`<div class=hint style="margin-top:12px">점선은 AI 추정입니다. 확인·수정 기능은 다음 단계에 붙습니다.</div>`;
 box.innerHTML=h}
// 끌어서 이동, 휠로 확대
let drag=null;svg.addEventListener("mousedown",e=>drag={x:e.clientX,y:e.clientY,v:[...view]});
window.addEventListener("mouseup",()=>drag=null);
svg.addEventListener("mousemove",e=>{if(!drag)return;const k=view[2]/svg.clientWidth;view[0]=drag.v[0]-(e.clientX-drag.x)*k;view[1]=drag.v[1]-(e.clientY-drag.y)*k;svg.setAttribute("viewBox",view.join(" "))});
svg.addEventListener("wheel",e=>{e.preventDefault();const f=e.deltaY>0?1.1:.9,r=svg.getBoundingClientRect(),px=(e.clientX-r.left)/r.width,py=(e.clientY-r.top)/r.height;
 const nw=view[2]*f,nh=view[3]*f;view=[view[0]+(view[2]-nw)*px,view[1]+(view[3]-nh)*py,nw,nh];svg.setAttribute("viewBox",view.join(" "))},{passive:false});
svg.addEventListener("click",()=>{if(sel){sel=null;draw();card(null)}});
document.querySelectorAll("#bar button[data-m]").forEach(b=>b.onclick=()=>{mode=b.dataset.m;document.querySelectorAll("#bar button[data-m]").forEach(x=>x.classList.toggle("on",x===b));draw()});
document.getElementById("fit").onclick=()=>{fit();draw()};
fit();draw();
</script></body></html>"""
