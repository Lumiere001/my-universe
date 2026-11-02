"use client";
// 별이 태어나는 대화(2026-11-03 동규 A안 「우주를 만드는 대화」 → 「너무 화려함, 깔끔하고 세련되게」): 가운데 빛 구슬 하나 + 가는 고리 하나.
//  걸려옴 = 구슬이 천천히 숨 쉼 · 대화 중 = 별지기가 말하면 구슬이 소리만큼 부풀고, 내가 말하면 고리가 밝아지며 빛 알갱이 몇 개가
//  천천히 구슬로 모인다. 내 말이 쌓일수록(grown) 구슬이 조금씩 밝아짐 · 끝 = 구슬이 작은 별 하나로 줄어 오른쪽 위로 올라가 자리 잡는다.
// read() 는 엔진의 소리 크기(0~1)와 지금 누가 말하는지. 투명 캔버스 하나를 우주 배경(CallCosmos) 위에 겹친다. 움직임 줄이기면 멈춘 한 장.
import { useEffect, useRef } from "react";

export type NebulaState = { stage: "ring" | "live" | "ended"; mode: "speaking" | "listening"; v: number };
type Mote = { a: number; d: number; life: number };

export default function CallNebula({ read, grown }: { read: () => NebulaState; grown: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const g = useRef(grown);
  g.current = grown;
  useEffect(() => {
    const cv = ref.current, ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const motes: Mote[] = [];
    let id = 0, last = performance.now(), endAt = 0, size = 40, ring = 0, carry = 0;
    const t0 = last;
    const draw = (now: number) => {
      const t = (now - t0) / 1000, dt = Math.min(.05, (now - last) / 1000);
      last = now;
      const s = read(), dpr = Math.min(2, devicePixelRatio || 1), W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const cx = W / 2, cy = H * .44, grow = Math.min(5, g.current);
      const speaking = s.stage === "live" && s.mode === "speaking", hearing = s.stage === "live" && s.mode === "listening";
      // 구슬 크기 · 고리 밝기는 부드럽게 따라간다
      const want = s.stage === "ring" ? 40 + 3 * Math.sin(t * 1.1) : 42 + grow * 2 + (speaking ? s.v * 22 : 0);
      size += (want - size) * Math.min(1, dt * 6);
      ring += ((hearing ? .25 + s.v * .6 : .14) - ring) * Math.min(1, dt * 6);
      if (s.stage === "ended") {
        endAt ||= t;
        const e = Math.min(1, (t - endAt) / 2.2), k = e * e * (3 - 2 * e), m = Math.max(0, k * 1.6 - .6);
        const fx = cx + (W * .9 - cx) * m, fy = cy + (H * .06 - cy) * m;   // 앞 40%는 제자리에서 줄고, 뒤 60%에 오른쪽 위 구석으로
        orb(ctx, fx, fy, Math.max(2.4, size * (1 - Math.min(1, k * 2.2))), .9);
        if (e >= 1) {   // 자리 잡은 뒤 가는 빛 한 줄기씩(조용히 반짝)
          const L = 7 + 2 * Math.sin(t * 1.6);
          ctx.strokeStyle = "rgba(255,255,255,.4)"; ctx.lineWidth = .8;
          ctx.beginPath(); ctx.moveTo(fx - L, fy); ctx.lineTo(fx + L, fy); ctx.moveTo(fx, fy - L); ctx.lineTo(fx, fy + L); ctx.stroke();
        }
      } else {
        // 가는 고리 하나: 내가 말할 때 밝아지고 소리만큼 조금 벌어진다
        ctx.strokeStyle = `rgba(255,255,255,${ring})`; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(cx, cy, size * 1.9 + (hearing ? s.v * 10 : 0), 0, 6.283); ctx.stroke();
        // 내 말 = 빛 알갱이 몇 개가 고리 밖에서 천천히 구슬로(많지 않게)
        if (hearing && s.v > .08 && !still) {
          carry += s.v * dt * 7;
          while (carry > 1) { carry -= 1; motes.push({ a: Math.random() * 6.283, d: size * 3.2, life: 1 }); }
        }
        for (let i = motes.length - 1; i >= 0; i--) {
          const p = motes[i];
          p.d -= dt * 38; p.a += dt * .25;
          if (p.d < size * .8) p.life -= dt * 3;
          if (p.life <= 0) { motes.splice(i, 1); continue; }
          ctx.fillStyle = `rgba(255,255,255,${.7 * p.life})`;
          ctx.fillRect(cx + Math.cos(p.a) * p.d, cy + Math.sin(p.a) * p.d, 1.2, 1.2);
        }
        orb(ctx, cx, cy, size, .55 + grow * .06 + (speaking ? s.v * .25 : 0));
      }
      if (!still && !document.hidden) id = requestAnimationFrame(draw);
    };
    id = requestAnimationFrame(draw);
    const wake = () => { if (!document.hidden && !still) { cancelAnimationFrame(id); last = performance.now(); id = requestAnimationFrame(draw); } };
    document.addEventListener("visibilitychange", wake);
    return () => { cancelAnimationFrame(id); document.removeEventListener("visibilitychange", wake); };
  }, [read]);
  return <canvas ref={ref} className="call-nebula" aria-hidden />;
}

// 빛 구슬: 흰 가운데에서 옅은 보라로, 바깥은 은은한 빛 한 겹(색은 하나만)
function orb(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, a: number) {
  const halo = ctx.createRadialGradient(x, y, r * .6, x, y, r * 2.4);
  halo.addColorStop(0, `rgba(190,174,255,${.18 * a})`); halo.addColorStop(1, "rgba(190,174,255,0)");
  ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(x, y, r * 2.4, 0, 6.283); ctx.fill();
  const body = ctx.createRadialGradient(x - r * .25, y - r * .3, r * .05, x, y, r);
  body.addColorStop(0, `rgba(255,255,255,${Math.min(1, a + .3)})`);
  body.addColorStop(.6, `rgba(214,204,255,${a})`);
  body.addColorStop(1, `rgba(150,128,240,${a * .6})`);
  ctx.fillStyle = body; ctx.beginPath(); ctx.arc(x, y, r, 0, 6.283); ctx.fill();
}
