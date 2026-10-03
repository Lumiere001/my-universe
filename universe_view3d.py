"""
universe_view3d.py

3D 우주 화면. 2D 화면(universe_view.py)과 같은 데이터(_payload)를 Three.js 로 띄운다.
글 = 별, 주제 = 행성(성운), 관계 = 별자리.
시간은 원반의 반지름이다: 첫 기록이 가운데, 최근 글일수록 바깥(첫 기억에서 퍼져 나가는 우주).
삶의 영역(D1..D9)마다 부채꼴 하나를 갖고, 별은 자기 영역 부채꼴 안에 놓인다.

기호 규칙은 2D 와 같다.
- 색은 두 뜻: 보라 = 이어지는 관계(이어짐 · 바뀜 · 해소), 주황 = 충돌(긴장 · 어긋남 · 목표 충돌)
- 실선 = 원문으로 확인, 점선 = AI 추정
- 별 크기 = 생각 수, 밝기 = 확신, 금색 고리 = 다짐(지켜지면 두껍게 채움), "?" = 질문
행성은 자기 부채꼴의 바깥 끝(가장 최근 고리 너머)에 놓는다. 달마다 희미한 고리를 그린다.

Three.js(r128)를 CDN 에서 읽는다. 못 읽으면 "평면 보기"로 돌아가라는 안내를 띄운다.
"""

import json

from universe_view import _payload


def render(state, selected=None, height=680):
    data = json.dumps(_payload(state, selected), ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__H__", str(int(height))).replace("__DATA__", data)


TEMPLATE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>
:root{--ink:#eef2ff;--mute:#a9b6dc;--line:#26407e;--violet:#a78bfa;--coral:#fb8a6b;--gold:#fcd679}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:transparent;color:var(--ink);font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR",system-ui,sans-serif}
#wrap{position:relative;height:min(__H__px,100vh);border:1px solid #1c3672;border-radius:14px;overflow:hidden;background:linear-gradient(180deg,#00133a 0%,#063a8f 50%,#1f5cc4 100%)}
#gl{position:absolute;inset:0;width:100%;height:100%;display:block;cursor:grab;touch-action:none}
#gl:active{cursor:grabbing}
#ov{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.hl{position:absolute;transform:translate(-50%,-100%);text-align:center;white-space:nowrap;font-weight:700;font-size:13px;line-height:1.15;color:#f4f7ff;text-shadow:0 1px 2px #00113a,0 0 8px #00133a,0 0 14px #00133a99}
.hl small{display:block;font-weight:500;font-size:10.5px;color:#c3d3f6}.hl small.tp{font-size:9.5px;color:#9fb3e0}.hl.dim{opacity:.7}
.ql{position:absolute;transform:translate(-50%,-50%);font-size:11px;font-weight:800;color:#ddd3ff;text-shadow:0 0 4px #2b1d86,0 0 8px #00133a}
.mon{position:absolute;transform:translate(-50%,-50%);padding:0 5px;border-radius:6px;background:#03163f99;font-size:11px;color:#d3e0fb;white-space:nowrap;text-shadow:0 0 6px #00133a}
.mon.end{color:#fff;font-weight:700}.mon.c{font-size:12.5px;font-weight:800;color:#fff;background:#03163fcc}
.sl{position:absolute;transform:translate(0,-50%);font-size:11.5px;white-space:nowrap;color:#fff;background:#071a46d9;border:1px solid #3a5aa8;border-radius:7px;padding:2px 7px}
#card{position:absolute;right:10px;top:10px;bottom:10px;width:min(330px,calc(100% - 20px));background:#0a1636f2;border:1px solid var(--line);border-radius:12px;overflow:auto;padding:16px 16px 24px;font-size:13px;line-height:1.55;display:none;box-shadow:0 8px 30px #0008}
#card .x{position:absolute;right:10px;top:8px;cursor:pointer;color:var(--mute);font-size:18px}
#card h3{margin:0 0 4px;font-size:16px;padding-right:18px}#card .sub{color:var(--mute);font-size:12px;margin-bottom:10px}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;margin-right:4px;border:1px solid var(--line);color:var(--mute)}
.badge.v{color:var(--violet);border-color:#4c3f86}
.th{border-top:1px solid var(--line);padding:9px 0}.q{color:var(--mute);font-style:italic;margin-top:3px}
.rel{border-left:3px solid var(--violet);padding:4px 8px;margin:6px 0;background:#12204a;border-radius:0 8px 8px 0}
.rel.c{border-left-color:var(--coral)}
#bar{position:absolute;left:12px;top:10px;display:flex;gap:6px;flex-wrap:wrap}
#bar button{background:#071a46cc;color:var(--ink);border:1px solid #33529c;border-radius:8px;padding:5px 10px;font-size:12px;cursor:pointer;font-family:inherit}
#bar button:hover{border-color:#6f8fe0}
#bar button.on{border-color:var(--violet);color:#cdbcff}
#legend{position:absolute;left:12px;bottom:10px;font-size:11px;color:#c6d2f2;background:#03163fcc;border:1px solid #23407f;border-radius:10px;padding:7px 10px;line-height:1.7;max-width:calc(100% - 24px)}
#legend i{display:inline-block;width:22px;height:0;border-top:2px solid;vertical-align:middle;margin-right:5px}
#legend .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 3px 0 6px;vertical-align:0}
#tip{position:absolute;pointer-events:none;background:#061535f0;border:1px solid #33529c;border-radius:8px;padding:5px 8px;font-size:12px;line-height:1.45;display:none;max-width:320px;z-index:5}
.hint{color:var(--mute)}
#hint{position:absolute;right:14px;top:12px;font-size:12px;color:#b9c7ea;text-shadow:0 0 6px #00133a}
#msg{position:absolute;inset:0;display:none;align-items:center;justify-content:center;text-align:center;padding:24px;font-size:15px;line-height:1.6;color:#eef2ff}
</style></head><body>
<script>window.onerror=function(m,s,l,c){var b=document.body;if(b)b.dataset.err=(b.dataset.err||"")+m+" @"+l+":"+c+"; "};</script>
<div id="wrap"><canvas id="gl"></canvas><div id="ov"></div>
<div id="bar"><button data-m="base" class="on">기본</button><button data-m="value">가치 보기</button><button id="home">처음 시점</button></div>
<div id="legend"><div><i style="border-color:var(--violet)"></i>이어짐 · 바뀜(화살표) · 해소(고리)</div>
<div><i style="border-color:var(--coral)"></i>긴장(쌍성) · 어긋남 · 목표 충돌</div>
<div><i style="border-color:#e3e9ff"></i>실선 = 원문으로 확인 &nbsp; <i style="border-color:#e3e9ff;border-top-style:dashed"></i>점선 = AI 추정</div>
<div>별 크기 = 생각 수 · 밝기 = 확신 · <span style="color:var(--gold)">◯</span> 다짐(채움 = 지킴) · <span style="color:#ddd3ff;font-weight:800">?</span> 질문</div>
<div>행성 = 삶의 영역 · 중심 = 처음 기록, 바깥 = 최근</div><div id="vleg" style="display:none"></div></div>
<div id="tip"></div><div id="hint">별을 누르면 그 글의 카드가 열립니다 · 끌어서 돌리기 · 휠로 확대</div>
<div id="card"></div>
<div id="msg">3D 화면을 불러오지 못했습니다. 위의 '평면 보기'를 눌러 주세요.</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
(function(){
const D=__DATA__;
const $=id=>document.getElementById(id);
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
const VAL={"자율":"#7dd3fc","도전":"#f472b6","즐거움":"#fde047","성취":"#fb923c","영향력":"#c084fc","안정":"#94a3b8","규범":"#a3e635","전통·신앙":"#fcd34d","배려":"#5eead4","공익":"#60a5fa"};
const CONF=new Set(["긴장","어긋남","목표 충돌"]);
const PAL=["#8fb8f6","#7ee2a6","#6fd3c4","#b3c6fb","#a6e8c4","#7cc4ee","#c8d6ff","#62c99a","#9ad7f2","#b9e9d6"];
function fail(){$("msg").style.display="flex";for(const id of ["bar","legend","hint"])$(id).style.display="none"}
if(typeof THREE==="undefined"||!THREE.OrbitControls){fail();return}
try{init()}catch(e){fail();throw e}

function init(){
const wrap=$("wrap"),canvas=$("gl"),ov=$("ov"),tip=$("tip");
const reduce=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches);
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setPixelRatio(Math.min(2,window.devicePixelRatio||1));
const scene=new THREE.Scene(),FOV=50;
const camera=new THREE.PerspectiveCamera(FOV,1,1,14000);scene.add(camera);
const controls=new THREE.OrbitControls(camera,canvas);
controls.enableDamping=true;controls.dampingFactor=.08;controls.rotateSpeed=.6;controls.zoomSpeed=.9;controls.panSpeed=.8;controls.screenSpacePanning=true;
// 빛은 카메라에 붙인다: 어느 방향에서 봐도 행성이 왼쪽 위에서 비친 구로 보인다
const sun=new THREE.DirectionalLight(0xffffff,1.1);sun.position.set(-.9,.9,.8);camera.add(sun);camera.add(sun.target);sun.target.position.set(0,0,-1);
scene.add(new THREE.AmbientLight(0x7d9be0,.42));

/* ---------- textures ---------- */
function rng(seed){let s=seed|0;return()=>{s=(s+0x6d2b79f5)|0;let t=Math.imul(s^(s>>>15),1|s);t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296}}
function cv(w,h,fn){const c=document.createElement("canvas");c.width=w;c.height=h;fn(c.getContext("2d"),w,h);return new THREE.CanvasTexture(c)}
function radial(stops){return cv(128,128,g=>{const gr=g.createRadialGradient(64,64,0,64,64,64);stops.forEach(([o,a])=>gr.addColorStop(o,"rgba(255,255,255,"+a+")"));g.fillStyle=gr;g.fillRect(0,0,128,128)})}
const SOFT=radial([[0,1],[.2,.6],[.5,.16],[1,0]]);
const CORE=radial([[0,1],[.3,.95],[.55,.35],[1,0]]);
const ATM=radial([[0,0],[.56,0],[.63,.6],[.76,.2],[1,0]]);
function ringTex(lw){return cv(128,128,g=>{g.strokeStyle="#fff";g.lineWidth=lw;g.beginPath();g.arc(64,64,60-lw/2,0,Math.PI*2);g.stroke()})}
const RING1=ringTex(6),RING2=ringTex(13);
const SPIKE=cv(128,128,g=>{for(const [dx,dy,len] of [[1,0,64],[0,1,46]]){const gr=g.createLinearGradient(64-dx*len,64-dy*len,64+dx*len,64+dy*len);gr.addColorStop(0,"rgba(255,255,255,0)");gr.addColorStop(.5,"rgba(255,255,255,.9)");gr.addColorStop(1,"rgba(255,255,255,0)");g.strokeStyle=gr;g.lineWidth=2;g.beginPath();g.moveTo(64-dx*len,64-dy*len);g.lineTo(64+dx*len,64+dy*len);g.stroke()}});
const DASH=cv(32,2,g=>{g.fillStyle="#000";g.fillRect(0,0,32,2);g.fillStyle="#fff";g.fillRect(0,0,18,2)});DASH.wrapS=THREE.RepeatWrapping;
// 하늘: 새벽 남색 그라디언트 + 성운 빛 + 오로라 커튼 + 먼 별가루 (한 번만 그린다)
scene.background=cv(1024,640,(g,w,h)=>{
 const gr=g.createLinearGradient(0,0,0,h);gr.addColorStop(0,"#00133a");gr.addColorStop(.5,"#063a8f");gr.addColorStop(1,"#1f5cc4");g.fillStyle=gr;g.fillRect(0,0,w,h);
 g.globalCompositeOperation="screen";
 for(const [x,y,rr,c,a] of [[.16,.34,.34,"130,178,246",.10],[.8,.58,.4,"104,214,154",.06],[.52,.16,.28,"160,196,252",.08]]){const q=g.createRadialGradient(x*w,y*h,0,x*w,y*h,rr*w);q.addColorStop(0,"rgba("+c+","+a+")");q.addColorStop(.4,"rgba("+c+","+a*.4+")");q.addColorStop(1,"rgba("+c+",0)");g.fillStyle=q;g.fillRect(0,0,w,h)}
 g.filter="blur(9px)";g.lineCap="round";
 for(const [cx,top,cw,ch,c,ph] of [[.22,.05,.36,.55,"130,178,246",0],[.6,.0,.44,.62,"104,214,154",1.3],[.88,.09,.3,.5,"160,196,252",2.1]]){
  const x0=(cx-cw/2)*w,x1=(cx+cw/2)*w,amp=.05;g.lineWidth=(x1-x0)/16*3.4;
  for(let i=0;i<16;i++){const u=(i+.5)/16,bell=Math.sin(u*Math.PI),a=.09*bell*bell*(1.9/3.4);
   const x=x0+(x1-x0)*u+Math.sin(u*2.7+ph*1.3)*amp*w*.18,yT=top*h+Math.sin(u*4.1+ph)*amp*h,yB=yT+ch*h*(.75+.35*Math.sin(u*2.3+ph*.8)),sk=Math.sin(u*1.7+ph*.6)*amp*w*.3;
   const lg=g.createLinearGradient(x,yT,x+sk,yB);lg.addColorStop(0,"rgba("+c+",0)");lg.addColorStop(.3,"rgba("+c+","+a*1.5+")");lg.addColorStop(.65,"rgba("+c+","+a*.7+")");lg.addColorStop(1,"rgba("+c+",0)");
   g.strokeStyle=lg;g.beginPath();g.moveTo(x,yT);g.lineTo(x+sk,yB);g.stroke()}}
 g.filter="none";g.globalCompositeOperation="source-over";
 const r=rng(3);for(let i=0;i<320;i++){g.globalAlpha=.08+r()*.32;g.fillStyle="#f2f7ff";g.beginPath();g.arc(r()*w,r()*h,.4+r()*.8,0,6.283);g.fill()}g.globalAlpha=1});

function sprite(tex,color,scale,op,add){const m=new THREE.Sprite(new THREE.SpriteMaterial({map:tex,color,transparent:true,opacity:op,depthWrite:false,blending:add?THREE.AdditiveBlending:THREE.NormalBlending,fog:!add}));m.scale.setScalar(scale);m.userData.op=op;return m}
function tubeC(curve,rad,color,op,dash,seg){const mat=new THREE.MeshBasicMaterial({color,transparent:true,opacity:op,depthWrite:false});
 if(dash){const t=DASH.clone();t.needsUpdate=true;t.repeat.set(Math.max(1,curve.getLength()/11),1);mat.alphaMap=t}
 const m=new THREE.Mesh(new THREE.TubeGeometry(curve,seg,rad,6,false),mat);m.userData.op=op;scene.add(m);return m}
function label(cls,html){const e=document.createElement("div");e.className=cls;e.innerHTML=html;ov.appendChild(e);return e}

/* 먼 별가루: 돌릴 때 하늘과 어긋나 움직이며 깊이감을 준다 */
function dust(n,size,op,seed,soft){const r=rng(seed),p=new Float32Array(n*3);for(let i=0;i<n;i++){const R=2600+r()*1800,t=r()*Math.PI*2,u=r()*2-1,q=Math.sqrt(1-u*u);p[i*3]=R*q*Math.cos(t);p[i*3+1]=R*u;p[i*3+2]=R*q*Math.sin(t)-300}
 const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(p,3));scene.add(new THREE.Points(g,new THREE.PointsMaterial({color:0xf2f7ff,size,sizeAttenuation:false,transparent:true,opacity:op,depthWrite:false,fog:false,map:soft?SOFT:null})))}
dust(1300,1.3,.5,7,false);dust(240,3.4,.75,11,true);

/* ---------- 시간 → 반지름 (첫 기록 = 가운데, 최근일수록 바깥) · 영역 → 부채꼴 ---------- */
const R0=50,R1=330,NH=Math.max(1,D.hubs.length),SEC=Math.PI*2/NH;
const dn=d=>{const t=Date.parse(String(d)+"T00:00:00Z");return isNaN(t)?null:Math.round(t/864e5)};
const ds=D.stars.map(s=>dn(s.day)).filter(v=>v!=null);
const d0=ds.length?Math.min(...ds):0,d1=ds.length?Math.max(...ds):0;
const rD=v=>d1>d0?R0+(R1-R0)*(Math.min(Math.max(v,d0),d1)-d0)/(d1-d0):(R0+R1)/2;
const rOf=d=>{const v=dn(d);return rD(v==null?d0:v)};
const ang=i=>-Math.PI/2+i*SEC;  // 2D 화면과 같은 순서: D1 이 위(먼 쪽)
const onDisc=(r,a,y)=>new THREE.Vector3(r*Math.cos(a),y,r*Math.sin(a));
const hubIdx={};D.hubs.forEach((h,i)=>hubIdx[h.id]=i);
const jr=rng(5);

/* ---------- 별 (글) ---------- */
const starObj={};
for(const s of D.stars){
 const top=(s.links||[]).slice().sort((a,b)=>(b.n||0)-(a.n||0))[0],hi=hubIdx[top?top.hub:s.near_hub];
 const a=hi==null?jr()*Math.PI*2:ang(hi)+(jr()-.5)*SEC*.72,p=onDisc(rOf(s.day),a,(jr()-.5)*36),n=s.n||0,b=+s.bright||.35,R=n?Math.min(3+n*1.05,8.4):2;
 const g=new THREE.Group();g.position.copy(p);scene.add(g);
 const o={s,p,R,g,list:[]},add=m=>{g.add(m);o.list.push(m);return m};
 add(sprite(SOFT,0xd6e6ff,R*(n?7:5),n?.16+.36*b:.12,true));
 add(sprite(CORE,0xffffff,R*2.3,n?.4+.6*b:.35,true));
 if(n>=3&&b>=.8)add(sprite(SPIKE,0xeaf2ff,R*6.5,.55,true));
 if(s.vow){if(s.vow==="kept")add(sprite(SOFT,0xfcd679,R*4.8,.4,false));add(sprite(s.vow==="kept"?RING2:RING1,0xfcd679,R*3.3,.95,false))}
 o.sel=sprite(RING1,0xffffff,R*5,0,false);g.add(o.sel);
 if(s.question)o.q=label("ql","?");
 starObj[s.id]=o}

/* ---------- 행성 (삶의 영역) — 자기 부채꼴 바깥 끝 ---------- */
const hubObj={};
D.hubs.forEach((h,i)=>{
 const cnt=h.count||0,r=cnt?9+5*Math.sqrt(cnt):6,col=new THREE.Color(PAL[i%PAL.length]),pos=onDisc(R1+70,ang(i),0);
 const mesh=new THREE.Mesh(new THREE.SphereGeometry(r,48,32),new THREE.MeshPhongMaterial({color:col,emissive:col.clone().multiplyScalar(.14),specular:0x5a6a80,shininess:26}));
 mesh.position.copy(pos);scene.add(mesh);
 const atm=sprite(ATM,col,r*3.2,.8,true);atm.position.copy(pos);scene.add(atm);
 if(cnt){const neb=sprite(SOFT,0x82b2f6,r*9,.14,true);neb.position.copy(pos);scene.add(neb)}else{mesh.material.transparent=true;mesh.material.opacity=.55}
 const tp=(h.topics||[]).slice(0,3).map(t=>esc(t.name)).join(" · ");
 hubObj[h.id]={h,pos,r,lab:label("hl"+(cnt?"":" dim"),esc(h.name)+"<small>"+(cnt?esc(cnt)+"편":"아직 관측 안 됨")+"</small>"+(tp?"<small class=tp>"+tp+"</small>":""))}});

/* ---------- 별 → 행성 선 ---------- */
const links=[];
for(const id in starObj){const o=starObj[id],s=o.s,ls=(s.links||[]).filter(l=>hubObj[l.hub]);
 const to=H=>new THREE.LineCurve3(o.p.clone(),H.pos.clone());
 if(!ls.length&&s.near_hub&&hubObj[s.near_hub]){links.push({id,mesh:tubeC(to(hubObj[s.near_hub]),.3,0x9aa3c7,.2,false,1),base:0x9aa3c7,op:.2,vals:[]})}
 for(const l of ls){const c=s.inner_tension?0xfb8a6b:0x9d8cf5,op=.3+.06*Math.min(l.n||1,4);links.push({id,mesh:tubeC(to(hubObj[l.hub]),.4+.16*Math.min(l.n||1,4),c,op,false,1),base:c,op,vals:l.values||[]})}}

/* ---------- 별자리 (관계) ---------- */
const relObjs=[],UP=new THREE.Vector3(0,1,0),ZA=new THREE.Vector3(0,0,1),CONE=new THREE.ConeGeometry(2.6,7,12);
for(const r of D.rels){const A=starObj[r.a],B=starObj[r.b];if(!A||!B)continue;
 const ab=B.p.clone().sub(A.p),L=ab.length();if(L<1)continue;const dir=ab.clone().divideScalar(L);
 const col=CONF.has(r.type)?0xfb8a6b:0xa78bfa,dash=r.line==="점선",op=dash?.78:.97,rad=(r.type==="이어짐"?.75:1)*(dash?1:1.25);
 const o={r,meshes:[],pts:[]};
 if(r.type==="긴장"){let pp=new THREE.Vector3().crossVectors(ab,UP);if(pp.length()<1e-3)pp.crossVectors(ab,ZA);pp.normalize();
  const k=Math.min(.22*L,46),mid=A.p.clone().add(B.p).multiplyScalar(.5);
  for(const sg of [1,-1]){const cu=new THREE.QuadraticBezierCurve3(A.p.clone(),mid.clone().addScaledVector(pp,k*sg),B.p.clone());o.meshes.push(tubeC(cu,rad,col,op,dash,32));o.pts.push(cu.getPoints(24))}}
 else{const arrow=r.type==="바뀜"||r.type==="해소";
  const s0=A.p.clone().addScaledVector(dir,Math.min(A.R+3,L*.3)),e0=B.p.clone().addScaledVector(dir,-Math.min(B.R+3+(arrow?7:0),L*.4));
  o.meshes.push(tubeC(new THREE.LineCurve3(s0,e0),rad,col,op,dash,1));o.pts.push([s0,e0]);
  if(arrow){const cone=new THREE.Mesh(CONE,new THREE.MeshBasicMaterial({color:col,transparent:true,opacity:op,depthWrite:false}));cone.position.copy(e0).addScaledVector(dir,3.5);cone.quaternion.setFromUnitVectors(UP,dir);cone.userData.op=op;scene.add(cone);o.meshes.push(cone)}
  if(r.type==="해소"){const ring=sprite(RING1,col,B.R*5.6,.65,false);ring.position.copy(B.p);scene.add(ring);o.meshes.push(ring)}}
 relObjs.push(o)}

/* ---------- 시간 고리 (기록이 있는 달마다 하나, 가운데 = 처음) ---------- */
const pts=[...Object.values(starObj).map(o=>o.p),...Object.values(hubObj).map(o=>o.pos)];
const bb=new THREE.Box3().setFromPoints(pts.length?pts:[new THREE.Vector3()]);
const months=[],LA=ang(Math.floor(NH*.72))+SEC/2;  // 달 글자는 두 영역 사이 빈 틈에 세운다
function orbit(r,op){const m=new THREE.Mesh(new THREE.RingGeometry(r-.8,r+.8,160),new THREE.MeshBasicMaterial({color:0xdbe6ff,transparent:true,opacity:op,side:THREE.DoubleSide,depthWrite:false}));m.rotation.x=-Math.PI/2;scene.add(m)}
if(d1>d0){const yms=[...new Set(D.stars.map(s=>String(s.day).slice(0,7)))].filter(k=>/^\d{4}-\d\d$/.test(k)).sort(),multiYear=yms.length&&yms[0].slice(0,4)!==yms[yms.length-1].slice(0,4);
 for(const ym of yms){const y=+ym.slice(0,4),m=+ym.slice(5)-1,r=rD(Math.max(Date.UTC(y,m,1)/864e5,d0));orbit(r,.26);
  months.push({e:label("mon",(multiYear&&(m===0||!months.length)?y+"년 ":"")+(m+1)+"월"),p:onDisc(r,LA,0)})}
 orbit(R1,.45);months.push({e:label("mon end","최근"),p:onDisc(R1,LA-SEC*.3,0)})}
months.push({e:label("mon c","처음"),p:new THREE.Vector3()});
const selLab=label("sl","");selLab.style.display="none";

/* ---------- 카메라 ---------- */
const C=bb.getCenter(new THREE.Vector3()),rad=bb.getSize(new THREE.Vector3()).length()/2;
const asp=wrap.clientWidth/Math.max(1,wrap.clientHeight),dist=rad/Math.sin(FOV*Math.PI/360)*.74*Math.max(1,1.4/asp);  // 좁은 화면이면 조금 물러선다
// 옅은 안개: 먼(오래된) 선과 행성이 하늘색으로 조금 가라앉아 깊이가 읽힌다
scene.fog=new THREE.Fog(0x063a8f,dist*.7,dist*2.6);
const HOME={pos:C.clone().add(new THREE.Vector3(0,Math.cos(.7),Math.sin(.7)).multiplyScalar(dist)),tgt:C.clone()};  // 위에서 40° 기울여 원반 전체
camera.position.copy(HOME.pos);controls.target.copy(HOME.tgt);controls.minDistance=dist*.12;controls.maxDistance=dist*2.6;
controls.autoRotate=!reduce;controls.autoRotateSpeed=.3;
let fl=null;
controls.addEventListener("start",()=>{controls.autoRotate=false;fl=null});
$("home").onclick=()=>{fl={t:0,p0:camera.position.clone(),t0:controls.target.clone(),p1:HOME.pos.clone(),t1:HOME.tgt.clone()}};

/* ---------- 화면 좌표 ---------- */
let W=1,Hh=1,FPX=1,vo=0,voT=0;const V=new THREE.Vector3();
// 카드가 열리면 화면 중심을 왼쪽으로 옮겨, 카드에 가리지 않은 쪽 가운데에 우주가 오게 한다
function applyVO(){if(Math.abs(vo)<.5)camera.clearViewOffset();else camera.setViewOffset(W,Hh,vo,0,W,Hh)}
function resize(){W=wrap.clientWidth;Hh=wrap.clientHeight;renderer.setSize(W,Hh,false);camera.aspect=W/Math.max(1,Hh);camera.updateProjectionMatrix();applyVO();FPX=Hh/2/Math.tan(FOV*Math.PI/360)}
window.addEventListener("resize",resize);resize();
function scr(p){V.copy(p).project(camera);return{x:(V.x+1)/2*W,y:(1-V.y)/2*Hh,ok:V.z>-1&&V.z<1}}
const pxr=(p,R)=>R*FPX/Math.max(1,camera.position.distanceTo(p));
function put(e,x,y,ok){if(!ok||x<-60||x>W+60||y<-40||y>Hh+40){e.style.display="none";return}e.style.display="";e.style.left=x+"px";e.style.top=y+"px"}
function placeLabels(){
 for(const id in hubObj){const o=hubObj[id],s=scr(o.pos);put(o.lab,s.x,s.y-pxr(o.pos,o.r)*1.08-4,s.ok)}
 for(const id in starObj){const o=starObj[id];if(!o.q)continue;const s=scr(o.p),pr=pxr(o.p,o.R);put(o.q,s.x+pr*1.5+5,s.y-pr*1.5-5,s.ok)}
 for(const m of months){const s=scr(m.p);put(m.e,s.x,s.y,s.ok)}
 if(sel&&!cardOn){const o=starObj[sel],s=scr(o.p);put(selLab,s.x+pxr(o.p,o.R)*2.6+8,s.y,s.ok)}}

/* ---------- 고르기 · 흐리게 ---------- */
let sel=null,mode="base",cardOn=false;
const relOn=o=>!sel||o.r.a===sel||o.r.b===sel;
function applyLook(){
 const on=sel?new Set([sel]):null;if(sel)for(const r of D.rels)if(r.a===sel||r.b===sel){on.add(r.a);on.add(r.b)}
 for(const id in starObj){const o=starObj[id],f=on&&!on.has(id)?.16:1;for(const m of o.list)m.material.opacity=m.userData.op*f;o.sel.material.opacity=id===sel?.9:0;if(o.q)o.q.style.opacity=f}
 for(const L of links){const f=on&&!on.has(L.id)?.25:1;let c=L.base,op=L.op;if(mode==="value"){const v=L.vals.find(v=>VAL[v]);c=v?VAL[v]:0x9aa3c7;op=v?.95:.25}L.mesh.material.color.set(c);L.mesh.material.opacity=op*f}
 for(const o of relObjs){const f=(sel?(relOn(o)?1.2:.07):1)*(mode==="value"?.3:1);for(const m of o.meshes)m.material.opacity=Math.min(1,m.userData.op*f)}
 if(sel){const s=starObj[sel].s;selLab.innerHTML=esc(s.day)+" · "+esc(s.title)}else selLab.style.display="none"}
function select(id){sel=id&&starObj[id]?id:null;applyLook()}
document.querySelectorAll("#bar button[data-m]").forEach(b=>b.onclick=()=>{mode=b.dataset.m;document.querySelectorAll("#bar button[data-m]").forEach(x=>x.classList.toggle("on",x===b));$("vleg").style.display=mode==="value"?"":"none";applyLook()});
const usedV=[...new Set(D.stars.flatMap(s=>(s.links||[]).flatMap(l=>l.values||[])))].filter(v=>VAL[v]);
$("vleg").innerHTML="선 색 = 가치"+usedV.map(v=>'<span class=dot style="background:'+VAL[v]+'"></span>'+esc(v)).join("");

/* ---------- 마우스 ---------- */
function segD(px,py,a,b){const dx=b.x-a.x,dy=b.y-a.y,l=dx*dx+dy*dy;let t=l?((px-a.x)*dx+(py-a.y)*dy)/l:0;t=Math.max(0,Math.min(1,t));return Math.hypot(px-a.x-t*dx,py-a.y-t*dy)}
function pick(mx,my){let best=null,bd=1e9;
 for(const id in starObj){const o=starObj[id],s=scr(o.p);if(!s.ok)continue;const d=Math.hypot(s.x-mx,s.y-my);if(d<Math.max(8,pxr(o.p,o.R*1.6))&&d<bd){bd=d;best={k:"star",id}}}
 if(best)return best;
 for(const id in hubObj){const o=hubObj[id],s=scr(o.pos);if(!s.ok)continue;const d=Math.hypot(s.x-mx,s.y-my);if(d<Math.max(8,pxr(o.pos,o.r))&&d<bd){bd=d;best={k:"hub",id}}}
 if(best)return best;
 for(const o of relObjs){if(!relOn(o))continue;for(const ps of o.pts){let prev=null;for(const p of ps){const s=scr(p);if(prev&&prev.ok&&s.ok){const d=segD(mx,my,prev,s);if(d<6&&d<bd){bd=d;best={k:"rel",o}}}prev=s}}}
 return best}
function hideTip(){tip.style.display="none"}
function showTip(e,html){const r=wrap.getBoundingClientRect();tip.innerHTML=html;tip.style.display="block";let x=e.clientX-r.left+14,y=e.clientY-r.top+14;
 if(x+tip.offsetWidth>W-6)x=Math.max(6,e.clientX-r.left-14-tip.offsetWidth);if(y+tip.offsetHeight>Hh-6)y=Math.max(6,e.clientY-r.top-14-tip.offsetHeight);tip.style.left=x+"px";tip.style.top=y+"px"}
function tipHTML(h){
 if(h.k==="star"){const s=starObj[h.id].s;return esc(s.day)+" · "+esc(s.title)+"<br><span class=hint>생각 "+esc(s.n)+"개</span>"}
 if(h.k==="hub"){const x=hubObj[h.id].h,t=(x.topics||[]).slice(0,6);return "<b>"+esc(x.name)+"</b> · "+(x.count?esc(x.count)+"편":"아직 관측 안 됨")+(t.length?"<br><span class=hint>"+t.map(q=>esc(q.name)+" "+esc(q.count)).join(" · ")+"</span>":"")}
 const r=h.o.r;return "<b>"+esc(r.type)+"</b> · "+esc(r.line)+" · "+esc(r.topic)+"<br>"+esc(r.aday)+" → "+esc(r.bday)+"<br><span class=hint>"+esc(r.why)+"</span>"+(r.axis?"<br>축: "+esc(r.axis):"")}
const rel=e=>{const r=canvas.getBoundingClientRect();return pick(e.clientX-r.left,e.clientY-r.top)};
let down=null;
canvas.addEventListener("pointerdown",e=>{down=[e.clientX,e.clientY];hideTip()});
canvas.addEventListener("pointermove",e=>{if(e.buttons){hideTip();return}const h=rel(e);canvas.style.cursor=h&&h.k==="star"?"pointer":"";if(h)showTip(e,tipHTML(h));else hideTip()});
canvas.addEventListener("pointerleave",hideTip);
canvas.addEventListener("pointerup",e=>{if(!down)return;const m=Math.hypot(e.clientX-down[0],e.clientY-down[1]);down=null;if(m>5)return;
 const h=rel(e);if(h&&h.k==="star"){select(h.id);card(h.id)}else{select(null);card(null)}});

/* ---------- 카드 (2D 화면과 같은 내용) ---------- */
function card(id){const c=id&&D.cards[id],box=$("card"),hint=$("hint");cardOn=!!c;voT=c&&W>620?Math.min(330,W-20)/2:0;if(!c){box.style.display="none";hint.style.display="";return}box.style.display="block";hint.style.display="none";
 const rels=D.rels.filter(r=>r.a===id||r.b===id);
 let h='<span class=x title="닫기">✕</span><h3>'+esc(c.title)+'</h3><div class=sub>'+esc(c.day)+' ('+esc(c.basis)+') · '+esc(c.type)+(c.state?' · 관측: '+esc(c.state):'')+'</div>';
 if(c.summary)h+='<div>'+esc(c.summary)+'</div>';
 if(c.question)h+='<div style="margin:8px 0;color:#c4b5fd">다음에 써 볼 질문 · '+esc(c.question)+'</div>';
 const ths=c.thoughts||[];h+='<div style="margin-top:10px;font-weight:700">선 위의 생각 '+ths.length+'개</div>';
 if(!ths.length)h+='<div class=hint>생각이 없는 글이라 가까운 성운에 희미하게만 이어 두었습니다.</div>';
 for(const t of ths)h+='<div class=th><span class="badge v">'+esc(t.kind)+'</span><span class=badge>'+esc(t.certainty)+'</span><span class=badge>'+esc(t.topic)+'</span>'+(t.value?'<span class=badge>'+esc(t.value)+'</span>':'')
  +'<div style="margin-top:4px">'+esc(t.thought)+'</div><div class=q>“'+esc(t.quote)+'”</div>'+(t.change?'<div style="color:var(--violet);margin-top:3px">스스로 쓴 변화: '+esc(t.change)+'</div>':'')+'</div>';
 if(rels.length){h+='<div style="margin-top:12px;font-weight:700">이 별의 별자리 '+rels.length+'개</div>';
  for(const r of rels){const other=r.a===id?r.bday:r.aday;h+='<div class="rel '+(CONF.has(r.type)?'c':'')+'"><b>'+esc(r.type)+'</b> · '+esc(r.line)+' · '+esc(r.topic)+' · '+(r.a===id?'→ ':'← ')+esc(other)+'<div class=hint>'+esc(r.why)+'</div>'+(r.axis?'<div class=hint>축: '+esc(r.axis)+'</div>':'')+'</div>'}}
 const m=c.meta||{},lab={triggers:"계기",addressee:"말 거는 대상",roles:"등장 관계",references:"참고한 것",period:"다루는 기간"};
 const mm=Object.keys(lab).filter(k=>m[k]&&m[k].length).map(k=>lab[k]+': '+m[k].map(esc).join(", "));
 if(mm.length)h+='<div class=hint style="margin-top:12px">'+mm.join("<br>")+'</div>';
 h+='<div class=hint style="margin-top:12px">점선은 AI 추정입니다. 확인·수정 기능은 다음 단계에 붙습니다.</div>';
 box.innerHTML=h;box.scrollTop=0;box.querySelector(".x").onclick=()=>{select(null);card(null)}}
window.openStar=id=>{select(id);card(id)};

/* ---------- 그리기 ---------- */
select(D.selected);
(function loop(){requestAnimationFrame(loop);
 if(fl){fl.t=Math.min(1,fl.t+.035);const e=1-Math.pow(1-fl.t,3);camera.position.lerpVectors(fl.p0,fl.p1,e);controls.target.lerpVectors(fl.t0,fl.t1,e);if(fl.t>=1)fl=null}
 if(vo!==voT){vo=Math.abs(voT-vo)>.5?vo+(voT-vo)*.18:voT;applyVO()}
 controls.update();
 camera.updateMatrixWorld();placeLabels();renderer.render(scene,camera)})();
}
})();
</script></body></html>"""
