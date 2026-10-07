"use client";
// 3D 우주 v8. 해 = 삶의 영역, 해 곁의 작은 별 = 세부 주제, 작은 별을 도는 행성 = 기록(order 가 작을수록 가까움).
// 1차(universe_view3d.py) 동작을 따른다: 해를 누르면 그 태양계로 다가가고, 빈 곳을 누르면 전체. 좁은 화면이면 물러서서 다 보이게.
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Settings, Universe } from "@/lib/api";

export type Pick = { kind: "planet" | "sun" | "north" | "blackhole" | "none"; id: string | null };
type Props = {
  data: Universe; selected: string | null; glow: Set<string> | null; crossLinks: Settings["cross_links"];
  onPick: (p: Pick) => void; children?: React.ReactNode;
};

const CONFLICT = new Set(["긴장", "어긋남", "목표 충돌"]);
const VIOLET = 0xb9a6ff, ORANGE = 0xffa184, GOLD = 0xfcd679;
const PAL = [0x8fb8f6, 0x7ee2a6, 0xf5b47e, 0xc8a6ff, 0x6fd3c4, 0xf09ac0, 0xb3c6fb, 0xe6d27a, 0x9ad7f2];
const FOV = 50;

function glowTex() {
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d")!, gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(.25, "rgba(255,255,255,.55)"); gr.addColorStop(.6, "rgba(255,255,255,.12)"); gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
const orbitR = (order: number) => 9 + order * 6;

export default function Universe3D({ data, selected, glow, crossLinks, onPick, children }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const apply = useRef<(sel: string | null, glow: Set<string> | null, cross: Settings["cross_links"]) => void>(() => {});
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  useEffect(() => {
    const el = wrap.current!;
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-label", "나의 우주 3D 보기. 해를 누르면 그 영역으로 다가가고 빈 곳을 누르면 전체로 돌아와요.");
    canvas.setAttribute("role", "img");
    el.prepend(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x061334);
    const camera = new THREE.PerspectiveCamera(FOV, 1, 1, 8000);
    scene.add(camera);
    const controls = new OrbitControls(camera, canvas);
    controls.enableDamping = true; controls.dampingFactor = .08; controls.rotateSpeed = .6; controls.screenSpacePanning = true;
    const light = new THREE.DirectionalLight(0xffffff, 1.6);
    light.position.set(-.9, .9, .8); camera.add(light); camera.add(light.target); light.target.position.set(0, 0, -1);
    scene.add(new THREE.AmbientLight(0x8aa4e8, .9));
    const GLOW = glowTex();
    const sprite = (color: number, scale: number, op: number) => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: GLOW, color, transparent: true, opacity: op, depthWrite: false, blending: THREE.AdditiveBlending }));
      s.scale.setScalar(scale); s.userData.op = op; scene.add(s); return s;
    };
    const labels: HTMLDivElement[] = [];
    const label = (cls: string, text: string) => { const d = document.createElement("div"); d.className = "lab " + cls; d.textContent = text; el.appendChild(d); labels.push(d); return d; };

    // 별가루
    {
      const n = 900, p = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const R = 1500 + Math.random() * 1500, t = Math.random() * Math.PI * 2, u = Math.random() * 2 - 1, q = Math.sqrt(1 - u * u);
        p.set([R * q * Math.cos(t), R * u, R * q * Math.sin(t)], i * 3);
      }
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(p, 3));
      scene.add(new THREE.Points(g, new THREE.PointsMaterial({ color: 0xe8efff, size: 1.6, sizeAttenuation: false, transparent: true, opacity: .7 })));
    }

    /* ---------- 배치 ---------- */
    const sunPos: Record<string, THREE.Vector3> = {}, sunR: Record<string, number> = {}, sunSys: Record<string, number> = {};
    const starPos: Record<string, THREE.Vector3> = {}, starSys: Record<string, number> = {};
    const planetPos: Record<string, THREE.Vector3> = {};
    const maxOrder = (sid: string) => Math.max(0, ...data.planets.filter((p) => p.star_id === sid).map((p) => p.order));
    // 태양계 크기를 먼저 구하고, 해들을 원 위에 겹치지 않게 놓는다
    for (const s of data.suns) {
      sunR[s.id] = 7 + 2.4 * Math.sqrt(s.planet_count || 1);
      const stars = data.stars.filter((x) => x.sun_id === s.id);
      const sys = Math.max(0, ...stars.map((x) => orbitR(maxOrder(x.id)) + 4));
      sunSys[s.id] = sunR[s.id] + 16 + sys * 2;
    }
    const circ = data.suns.reduce((a, s) => a + sunSys[s.id] * 2.2, 0);
    const ringR = data.suns.length > 1 ? circ / (2 * Math.PI) : 0;
    let acc = 0;
    data.suns.forEach((s, i) => {
      const a = ((acc + sunSys[s.id] * 1.1) / Math.max(1, circ)) * Math.PI * 2;
      acc += sunSys[s.id] * 2.2;
      const pos = new THREE.Vector3(Math.cos(a) * ringR, 0, Math.sin(a) * ringR);
      sunPos[s.id] = pos;
      const col = PAL[i % PAL.length];
      const m = new THREE.Mesh(new THREE.SphereGeometry(sunR[s.id], 40, 28), new THREE.MeshBasicMaterial({ color: col }));
      m.position.copy(pos); scene.add(m);
      sprite(col, sunR[s.id] * 6, .55).position.copy(pos);
      const stars = data.stars.filter((x) => x.sun_id === s.id);
      stars.forEach((st, j) => {
        const sys = orbitR(maxOrder(st.id)) + 4;
        const b = (j / Math.max(1, stars.length)) * Math.PI * 2 + i;
        const sp = pos.clone().add(new THREE.Vector3(Math.cos(b), 0, Math.sin(b)).multiplyScalar(sunR[s.id] + 10 + sys));
        starPos[st.id] = sp; starSys[st.id] = sys;
        const sm = new THREE.Mesh(new THREE.SphereGeometry(2.6, 20, 14), new THREE.MeshBasicMaterial({ color: 0xfff4d6 }));
        sm.position.copy(sp); scene.add(sm);
        sprite(0xfff1c4, 16, .6).position.copy(sp);
        for (let o = 0; o <= maxOrder(st.id); o++) {
          const r = orbitR(o), ring = new THREE.Mesh(new THREE.RingGeometry(r - .25, r + .25, 96),
            new THREE.MeshBasicMaterial({ color: 0xdbe6ff, transparent: true, opacity: .22, side: THREE.DoubleSide, depthWrite: false }));
          ring.rotation.x = -Math.PI / 2; ring.position.copy(sp); scene.add(ring);
        }
        labels.push(Object.assign(label("star", st.name), { _p: sp, _dy: 6, _min: [sp, sys, 34] as const }));
      });
      labels.push(Object.assign(label("sun", `${s.name} · ${s.planet_count}편`), { _p: pos, _dy: sunR[s.id] + 3 }));
    });

    /* ---------- 행성 (기록) ---------- */
    type PObj = { id: string; mesh: THREE.Mesh; halo: THREE.Sprite; ring?: THREE.Mesh; sel: THREE.Sprite };
    const pobj: Record<string, PObj> = {};
    const PG = new THREE.SphereGeometry(2.3, 24, 16);
    for (const p of data.planets) {
      const c = starPos[p.star_id]; if (!c) continue;
      const a = p.order * 2.4 + p.star_id.length, pos = c.clone().add(new THREE.Vector3(Math.cos(a), 0, Math.sin(a)).multiplyScalar(orbitR(p.order)));
      planetPos[p.id] = pos;
      const mesh = new THREE.Mesh(PG, new THREE.MeshPhongMaterial({ color: 0xcfdcff, emissive: 0x24345f, shininess: 30, transparent: true }));
      mesh.position.copy(pos); scene.add(mesh);
      const halo = sprite(0xd6e6ff, 9, .35); halo.position.copy(pos);
      const sel = sprite(0xffffff, 16, 0); sel.position.copy(pos);
      const o: PObj = { id: p.id, mesh, halo, sel };
      if (p.ring) {  // 금빛 고리 = 열린 다짐
        const ring = new THREE.Mesh(new THREE.RingGeometry(3.4, 4.3, 48), new THREE.MeshBasicMaterial({ color: GOLD, side: THREE.DoubleSide, transparent: true, opacity: .95 }));
        ring.position.copy(pos); ring.rotation.x = -Math.PI / 2.6; scene.add(ring); o.ring = ring;
      }
      pobj[p.id] = o;
    }

    /* ---------- 이어진 선 · 쌍행성 ---------- */
    type LObj = { line: THREE.Line; a: string; b: string; cross: boolean; op: number };
    const lobj: LObj[] = [];
    const addLine = (pts: THREE.Vector3[], color: number, dashed: boolean, a: string, b: string, cross: boolean, op = .9) => {
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      const mat = dashed ? new THREE.LineDashedMaterial({ color, dashSize: 2.2, gapSize: 1.6, transparent: true, opacity: op })
        : new THREE.LineBasicMaterial({ color, transparent: true, opacity: op });
      const line = new THREE.Line(g, mat); if (dashed) line.computeLineDistances();
      scene.add(line); lobj.push({ line, a, b, cross, op }); return line;
    };
    for (const l of data.links) {
      const A = planetPos[l.from_planet], B = planetPos[l.to_planet]; if (!A || !B || l.type === "긴장") continue;
      const mid = A.clone().add(B).multiplyScalar(.5).add(new THREE.Vector3(0, A.distanceTo(B) * .12, 0));
      addLine(new THREE.QuadraticBezierCurve3(A, mid, B).getPoints(24), CONFLICT.has(l.type) ? ORANGE : VIOLET, l.line === "점선", l.from_planet, l.to_planet, l.cross_domain);
    }
    // 긴장 선(영역을 넘는 것 포함)은 쌍행성처럼 두 갈래 곡선으로
    const tension = [
      ...data.twins.map((t) => ({ a: t.a_planet, b: t.b_planet, open: t.status !== "해소", cross: false, dashed: false })),
      ...data.links.filter((l) => l.type === "긴장").map((l) => ({ a: l.from_planet, b: l.to_planet, open: true, cross: l.cross_domain, dashed: l.line === "점선" })),
    ];
    for (const t of tension) {
      const A = planetPos[t.a], B = planetPos[t.b]; if (!A || !B) continue;
      const ab = B.clone().sub(A), side = new THREE.Vector3().crossVectors(ab, new THREE.Vector3(0, 1, 0)).normalize(), k = Math.min(ab.length() * .18, 14);
      for (const sg of [1, -1]) {
        const mid = A.clone().add(B).multiplyScalar(.5).addScaledVector(side, k * sg);
        addLine(new THREE.QuadraticBezierCurve3(A, mid, B).getPoints(24), t.open ? ORANGE : VIOLET, t.dashed, t.a, t.b, t.cross, t.open ? .9 : .35);
      }
      if (t.open && !t.cross) for (const id of [t.a, t.b]) if (pobj[id]) { pobj[id].halo.material.color.set(ORANGE); pobj[id].halo.userData.color = ORANGE; }
    }

    /* ---------- 블랙홀 · 북극성 ---------- */
    const bh: Record<string, THREE.Vector3> = {};
    for (const b of data.blackholes) {
      const sp = starPos[b.star_id]; if (!sp) continue;
      const sun = data.stars.find((s) => s.id === b.star_id)!.sun_id;
      const out = sp.clone().sub(sunPos[sun]).setY(0).normalize();
      const r = 2.5 + b.size * 1.4, pos = sp.clone().addScaledVector(out, starSys[b.star_id] + r + 6);
      bh[b.id] = pos;
      sprite(0xff9a6b, r * 7, .45).position.copy(pos);
      const disk = new THREE.Mesh(new THREE.RingGeometry(r * 1.15, r * 1.9, 64), new THREE.MeshBasicMaterial({ color: 0xffb37a, side: THREE.DoubleSide, transparent: true, opacity: .7 }));
      disk.position.copy(pos); disk.rotation.x = -Math.PI / 2.3; scene.add(disk);
      const hole = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 20), new THREE.MeshBasicMaterial({ color: 0x000000 }));
      hole.position.copy(pos); scene.add(hole);
      labels.push(Object.assign(label("", "블랙홀 · " + b.label), { _p: pos, _dy: r * 2 + 2, _min: [pos, r * 2, 16] as const }));
    }

    const pts = [...Object.values(planetPos), ...Object.values(sunPos), ...Object.values(bh)];
    const box = new THREE.Box3().setFromPoints(pts.length ? pts : [new THREE.Vector3()]).expandByScalar(20);
    const size = box.getSize(new THREE.Vector3());
    // 우주는 납작한 원반이라 가로 · 세로(x, z)만 본다. 대각선의 0.6배: 돌려도 거의 잘리지 않으면서 휴대폰에서 작아지지 않게
    const C = box.getCenter(new THREE.Vector3()), rad = Math.hypot(size.x, size.z) * .6;
    let north: THREE.Vector3 | null = null;
    if (data.north_star) {
      north = C.clone().add(new THREE.Vector3(0, rad * .55, -rad * .35));
      sprite(GOLD, 46, .9).position.copy(north);
      sprite(0xffffff, 14, 1).position.copy(north);
      labels.push(Object.assign(label("north", "북극성"), { _p: north, _dy: 10 }));
    }

    /* ---------- 카메라 ---------- */
    let W = 1, H = 1;
    // 세로 · 가로 시야 중 좁은 쪽에 r 이 다 들어오는 거리(좁은 휴대폰 화면이면 물러선다)
    const fitDist = (r: number) => {
      const v = (FOV * Math.PI) / 360, h = Math.atan(Math.tan(v) * (W / Math.max(1, H)));
      return (r / Math.sin(Math.min(v, h))) * .8;
    };
    const view = (target: THREE.Vector3, r: number) => ({ pos: target.clone().add(new THREE.Vector3(0, Math.cos(.75), Math.sin(.75)).multiplyScalar(fitDist(r))), tgt: target.clone() });
    const resize = () => {
      W = el.clientWidth; H = el.clientHeight;
      renderer.setSize(W, H, false); camera.aspect = W / Math.max(1, H); camera.updateProjectionMatrix();
    };
    resize();
    let home = view(C, rad);
    camera.position.copy(home.pos); controls.target.copy(home.tgt);
    controls.maxDistance = fitDist(rad) * 2.5; controls.minDistance = 12;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    controls.autoRotate = !reduce; controls.autoRotateSpeed = .25;
    let fly: { t: number; p0: THREE.Vector3; t0: THREE.Vector3; p1: THREE.Vector3; t1: THREE.Vector3 } | null = null;
    const flyTo = (v: { pos: THREE.Vector3; tgt: THREE.Vector3 }) => {
      if (reduce) { camera.position.copy(v.pos); controls.target.copy(v.tgt); return; }
      fly = { t: 0, p0: camera.position.clone(), t0: controls.target.clone(), p1: v.pos, t1: v.tgt };
    };
    controls.addEventListener("start", () => { controls.autoRotate = false; fly = null; });
    const ro = new ResizeObserver(() => { resize(); home = view(C, rad); });
    ro.observe(el);

    /* ---------- 화면 좌표 · 고르기 ---------- */
    const V = new THREE.Vector3();
    const scr = (p: THREE.Vector3) => { V.copy(p).project(camera); return { x: (V.x + 1) / 2 * W, y: (1 - V.y) / 2 * H, ok: V.z > -1 && V.z < 1 }; };
    const pxr = (p: THREE.Vector3, r: number) => (r * H / 2 / Math.tan((FOV * Math.PI) / 360)) / Math.max(1, camera.position.distanceTo(p));
    const nearest = (mx: number, my: number, pos: Record<string, THREE.Vector3>, r: (id: string) => number, minPx: number) => {
      let best: string | null = null, bd = 1e9;
      for (const id in pos) {
        const s = scr(pos[id]); if (!s.ok) continue;
        const d = Math.hypot(s.x - mx, s.y - my);
        if (d < Math.max(minPx, pxr(pos[id], r(id))) && d < bd) { bd = d; best = id; }
      }
      return best;
    };
    const pick = (mx: number, my: number): Pick => {
      let id = nearest(mx, my, planetPos, () => 4, 16); if (id) return { kind: "planet", id };
      if (north && Math.hypot(scr(north).x - mx, scr(north).y - my) < 22) return { kind: "north", id: null };
      id = nearest(mx, my, bh, () => 8, 16); if (id) return { kind: "blackhole", id };
      id = nearest(mx, my, sunPos, (s) => sunR[s] * 1.3, 18); if (id) return { kind: "sun", id };
      const st = nearest(mx, my, starPos, () => 5, 14);
      if (st) return { kind: "sun", id: data.stars.find((s) => s.id === st)!.sun_id };
      return { kind: "none", id: null };
    };
    let down: [number, number] | null = null;
    const onDown = (e: PointerEvent) => { down = [e.clientX, e.clientY]; };
    const onUp = (e: PointerEvent) => {
      if (!down) return;
      const moved = Math.hypot(e.clientX - down[0], e.clientY - down[1]); down = null;
      if (moved > 6) return;
      const r = canvas.getBoundingClientRect(), p = pick(e.clientX - r.left, e.clientY - r.top);
      if (p.kind === "sun") flyTo(view(sunPos[p.id!], sunSys[p.id!] * 1.25));
      if (p.kind === "none") flyTo(home);
      pickRef.current(p);
    };
    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointerup", onUp);
    // 시험(Playwright)에서 행성 · 해를 화면 좌표로 누르기 위한 창구
    const all: Record<string, THREE.Vector3> = { ...planetPos, ...sunPos, ...(north ? { north } : {}) };
    (window as unknown as { __uni?: unknown }).__uni = {
      xy: (id: string) => { const r = canvas.getBoundingClientRect(), s = scr(all[id]); return { x: r.left + s.x, y: r.top + s.y }; },
    };

    /* ---------- 고른 것 · 빛남 · 영역 넘는 선 ---------- */
    apply.current = (sel, g, cross) => {
      for (const id in pobj) {
        const o = pobj[id], dim = g ? !g.has(id) : false, lit = g?.has(id);
        (o.mesh.material as THREE.MeshPhongMaterial).opacity = dim ? .3 : 1;
        (o.mesh.material as THREE.MeshPhongMaterial).emissive.set(lit ? 0x8a7a2a : 0x24345f);
        o.halo.material.opacity = dim ? .06 : lit ? 1 : o.halo.userData.op;
        o.halo.scale.setScalar(lit ? 24 : 9);
        o.halo.material.color.set(lit ? GOLD : o.halo.userData.color ?? 0xd6e6ff);
        o.sel.material.opacity = id === sel ? .9 : 0;
        if (o.ring) (o.ring.material as THREE.MeshBasicMaterial).opacity = dim ? .25 : .95;
      }
      for (const l of lobj) {
        const touch = !!sel && (l.a === sel || l.b === sel);
        l.line.visible = !l.cross || cross === "항상" || (cross === "눌렀을 때" && touch);
        (l.line.material as THREE.LineBasicMaterial).opacity = sel ? (touch ? 1 : l.op * .25) : l.op;
      }
    };

    /* ---------- 그리기 ---------- */
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      if (fly) {
        fly.t = Math.min(1, fly.t + .04); const k = 1 - Math.pow(1 - fly.t, 3);
        camera.position.lerpVectors(fly.p0, fly.p1, k); controls.target.lerpVectors(fly.t0, fly.t1, k);
        if (fly.t >= 1) fly = null;
      }
      controls.update(); camera.updateMatrixWorld();
      for (const d of labels as (HTMLDivElement & { _p?: THREE.Vector3; _dy?: number; _min?: readonly [THREE.Vector3, number, number] })[]) {
        if (!d._p) continue;
        const s = scr(d._p), up = pxr(d._p, d._dy ?? 0);
        const show = (!d._min || pxr(d._min[0], d._min[1]) >= d._min[2]) && s.ok && s.x > -40 && s.x < W + 40 && s.y > -20 && s.y < H + 20;
        d.style.display = show ? "" : "none";
        if (show) { d.style.left = s.x + "px"; d.style.top = s.y - up - 2 + "px"; }
      }
      renderer.render(scene, camera);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); renderer.dispose();
      canvas.removeEventListener("pointerdown", onDown); canvas.removeEventListener("pointerup", onUp);
      labels.forEach((d) => d.remove()); canvas.remove();
      scene.traverse((o) => { const m = o as THREE.Mesh; m.geometry?.dispose?.(); });
    };
  }, [data]);

  useEffect(() => { apply.current(selected, glow, crossLinks); }, [selected, glow, crossLinks, data]);

  // 캔버스와 이름표는 React 가 건드리지 않는 안쪽 칸에 둔다. children 은 그 위에 뜨는 도구 · 카드.
  return (
    <div className="uni" data-testid="universe">
      <div ref={wrap} style={{ position: "absolute", inset: 0 }} />
      {children}
    </div>
  );
}
