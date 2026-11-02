"use client";
// 대화 배경 = 내 우주(2026-11-03 동규 「oss-hub 랜딩처럼 행성 화면, 우리 테마로」 → 「너무 화려함, 깔끔하고 세련되게」).
// 검은 바탕에 그 사람의 해 · 행성을 작고 희미한 흰 점으로만(빛 십자 · 선 · 색 번짐 없음). 테마 색은 바닥의 아주 옅은 빛에만.
// 아주 천천히 돌고 처음에 조금 다가온다. 해 이름은 쓰지 않는다. 가운데는 빛 구슬(CallNebula). 움직임 줄이기면 한 장만 그린다.
import { useEffect, useRef } from "react";
import { themeColors } from "@/components/universeLook";
import type { Universe } from "@/lib/api";

type Pt = { x: number; y: number; z: number; r: number; a: number };
// 같은 우주는 늘 같은 모양(새로 열 때마다 흩어지지 않게): 글자 → 0~1
const hash = (s: string, k: number) => { let h = 2166136261 ^ k; for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return ((h >>> 0) % 10000) / 10000; };

function place(data: Universe | null, theme?: string | null) {
  const suns = (data?.suns ?? []).filter((s) => s.planet_count > 0);
  const at = new Map(suns.map((s, i) => {
    const a = (i / Math.max(1, suns.length)) * Math.PI * 2 + .4;
    return [s.id, { x: Math.cos(a) * 1.5, y: (hash(s.id, 1) - .5) * .8, z: Math.sin(a) * 1.5 }];
  }));
  const pts: Pt[] = [...at.values()].map((p) => ({ ...p, r: 1.8, a: .55 }));   // 해: 조금 큰 점
  for (const p of data?.planets ?? []) {   // 행성: 제 해 둘레의 작은 점
    const s = at.get(p.sun_id);
    if (!s) continue;
    const u = hash(p.id, 2) * Math.PI * 2, v = Math.acos(hash(p.id, 3) * 2 - 1), d = .3 + hash(p.id, 4) * .5;
    pts.push({ x: s.x + Math.sin(v) * Math.cos(u) * d, y: s.y + Math.cos(v) * d * .6, z: s.z + Math.sin(v) * Math.sin(u) * d, r: .9, a: .32 });
  }
  const dust = Array.from({ length: 80 }, (_, k) => ({ x: hash(String(k), 5), y: hash(String(k), 6), a: .06 + hash(String(k), 7) * .2 }));
  const bg = themeColors(theme).bg;
  return { pts, dust, tint: `rgba(${(bg >> 16) & 255},${(bg >> 8) & 255},${bg & 255},.55)` };
}

export default function CallCosmos({ data, theme, dim = 0 }: { data: Universe | null; theme?: string | null; dim?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current, ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    const w = place(data, theme);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const t0 = performance.now();
    let id = 0;
    const draw = (now: number) => {
      const t = still ? 6 : (now - t0) / 1000;
      const dpr = Math.min(2, devicePixelRatio || 1), W = cv.clientWidth, H = cv.clientHeight;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);
      const sky = ctx.createRadialGradient(W * .5, H * 1.05, 0, W * .5, H * 1.05, H * .9);   // 테마 색은 바닥에만 아주 옅게
      sky.addColorStop(0, w.tint); sky.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = sky; ctx.fillRect(0, 0, W, H);
      for (const d of w.dust) { ctx.fillStyle = `rgba(255,255,255,${d.a})`; ctx.fillRect(d.x * W, d.y * H, 1, 1); }
      // 카메라: 아주 천천히 돌고(0.03 rad/s), 처음 4초에 조금 다가온다
      const yaw = t * .03, tilt = .38, near = 1 - Math.pow(1 - Math.min(1, t / 4), 3), D = 4.4 - near * 1.2;
      const F = Math.min(W, H) * .95, cx = W / 2, cy = H * .46;
      for (const p of w.pts) {
        const x1 = p.x * Math.cos(yaw) - p.z * Math.sin(yaw), z1 = p.x * Math.sin(yaw) + p.z * Math.cos(yaw);
        const y2 = p.y * Math.cos(tilt) - z1 * Math.sin(tilt), z2 = p.y * Math.sin(tilt) + z1 * Math.cos(tilt) + D;
        const s = F / z2, depth = Math.max(.35, Math.min(1, 3.6 / z2));
        ctx.fillStyle = `rgba(255,255,255,${p.a * depth})`;
        ctx.beginPath(); ctx.arc(cx + x1 * s * .78, cy + y2 * s * .78, p.r * Math.min(1.4, s / (F / 3.2)), 0, 6.283); ctx.fill();
      }
      if (!still && !document.hidden) id = requestAnimationFrame(draw);
    };
    id = requestAnimationFrame(draw);
    const wake = () => { if (!document.hidden && !still) { cancelAnimationFrame(id); id = requestAnimationFrame(draw); } };
    document.addEventListener("visibilitychange", wake);
    return () => { cancelAnimationFrame(id); document.removeEventListener("visibilitychange", wake); };
  }, [data, theme]);
  return <canvas ref={ref} className="call-cosmos" style={{ opacity: 1 - dim }} aria-hidden />;
}
