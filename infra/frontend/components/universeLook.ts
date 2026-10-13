// 우주의 색 · 모양 값과 '값 → 모양' 규칙을 한곳에. 꾸미기(테마 색 · WS25)는 이 파일만 바꾸면 된다.
// 규칙은 PRD §7 '우주의 기호(v8)': 행성 크기 = 생각 수, 밝기 = 확신, '?' = 질문 / §9 '3D 중심': 다른 태양계와 연결이 가장 많은 해를 가운데에.
import type { Universe } from "@/lib/api";

export const COLOR = {
  bg: 0x061334, ambient: 0x8aa4e8, dust: 0xe8efff,
  violet: 0xb9a6ff, orange: 0xffa184, gold: 0xfcd679,
  ended: 0x7f88a6,                          // 끝난 목표 충돌(두 다짐 중 하나가 닫힘): 흐린 회색 점선
  star: 0xfff4d6, starGlow: 0xfff1c4, orbit: 0xdbe6ff,
  planet: 0xcfdcff, planetEmissive: 0x24345f, planetHalo: 0xd6e6ff, lit: 0x8a7a2a,
  hole: 0x000000, holeGlow: 0xff9a6b, holeDisk: 0xffb37a,
};
export const SUN_PALETTE = [0x8fb8f6, 0x7ee2a6, 0xf5b47e, 0xc8a6ff, 0x6fd3c4, 0xf09ac0, 0xb3c6fb, 0xe6d27a, 0x9ad7f2];
export const CONFLICT = new Set(["긴장", "어긋남", "목표 충돌"]);
export const PLANET_R = 2.3;

// 확신 → 밝기(0~1). 값이 없거나 목록 밖이면 가운데.
const LIGHT: Record<string, number> = { "단정": 1, "고민 중": .6, "판단 보류": .3 };

export function planetLook(p: { thought_count?: number; certainty?: string | null }) {
  const n = Math.max(1, p.thought_count ?? 1);
  // 생각 1개 = 1배, 4개 = 1.3배, 9개 = 1.6배. ponytail: 1.8배에서 멈춤(이웃 궤도와 겹치지 않게)
  return { scale: Math.min(1.8, .7 + .3 * Math.sqrt(n)), light: LIGHT[p.certainty ?? ""] ?? .6 };
}

// 가운데 해: 다른 태양계와 이어진 선(links · 쌍행성)이 가장 많은 해. 같으면 기록이 많은 해, 그래도 같으면 먼저 온 해.
export function centerSun(d: Pick<Universe, "suns" | "planets" | "links" | "twins">): string | null {
  const sunOf = new Map(d.planets.map((p) => [p.id, p.sun_id]));
  const n = new Map<string, number>();
  for (const [a, b] of [...d.links.map((l) => [l.from_planet, l.to_planet]), ...d.twins.map((t) => [t.a_planet, t.b_planet])]) {
    const x = sunOf.get(a), y = sunOf.get(b);
    if (x && y && x !== y) for (const s of [x, y]) n.set(s, (n.get(s) ?? 0) + 1);
  }
  let best: string | null = null, bn = -1, bc = -1;
  for (const s of d.suns) {
    const k = n.get(s.id) ?? 0;
    if (k > bn || (k === bn && s.planet_count > bc)) { best = s.id; bn = k; bc = s.planet_count; }
  }
  return best;
}
