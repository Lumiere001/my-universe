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

// 꾸미기(WS25): 테마는 바탕 · 해 · 별 · 행성 색만 바꾼다. 뜻이 있는 색(선 보라 · 맞섬 주황 · 다짐 금빛 · 블랙홀)은 범례와 맞게 그대로.
// 첫 테마 = 기본(지금 모습). 이름은 백엔드 SettingsPatch.theme 목록과 같아야 한다(tests/test_ws25_decorate.py 가 대조).
type Tint = Pick<typeof COLOR, "bg" | "ambient" | "dust" | "star" | "starGlow" | "orbit" | "planet" | "planetEmissive" | "planetHalo">;
export const THEMES = {
  "밤하늘": { ...COLOR, sun: SUN_PALETTE },
  "새벽": { bg: 0x1a1030, ambient: 0xc9a8e8, dust: 0xffe6f0, star: 0xffe9d6, starGlow: 0xffd9c4, orbit: 0xf0dcff,
    planet: 0xf2d6ff, planetEmissive: 0x3e2452, planetHalo: 0xffd6ec,
    sun: [0xf7a8c4, 0xffc58f, 0xc9a6ff, 0xffb3a1, 0xe8a8f0, 0xffd98f, 0xb8b0ff, 0xf5c2d8, 0xd9b8ff] },
  "오로라": { bg: 0x03181c, ambient: 0x8fe0cf, dust: 0xe0fff6, star: 0xf0fff4, starGlow: 0xd4ffe8, orbit: 0xc8fff0,
    planet: 0xc8f5ea, planetEmissive: 0x123f3a, planetHalo: 0xc4ffe9,
    sun: [0x6fe3b4, 0x63d2e6, 0xa8f08f, 0x8fb8ff, 0x52e0c4, 0xc8f57e, 0x7ec8f5, 0xb4a6ff, 0x9af2d6] },
  "먹": { bg: 0x0b0b0e, ambient: 0xc4c4cc, dust: 0xf2f2f2, star: 0xffffff, starGlow: 0xf0f0f0, orbit: 0xe8e8e8,
    planet: 0xdedee4, planetEmissive: 0x2a2a30, planetHalo: 0xeeeeee,
    sun: [0xd8d8de, 0xb8bcc8, 0xe8e2d4, 0xc4c8d0, 0xa8acb8, 0xeceae4, 0xc8c4bc, 0xb0b4bc, 0xdcdce4] },
} satisfies Record<string, Tint & { sun: number[] }>;
export type ThemeName = keyof typeof THEMES;
export const THEME_NAMES = Object.keys(THEMES) as ThemeName[];
export const themeOf = (t?: string | null): ThemeName => (t && t in THEMES ? t as ThemeName : "밤하늘");
export const themeColors = (t?: string | null) => ({ ...COLOR, ...THEMES[themeOf(t)] });

// 별지기 모습: '글자' = 지금처럼 이름 첫 글자, 나머지는 public/keeper/<이름>.svg (백엔드 SettingsPatch.keeper_look 과 같은 목록)
export const KEEPER_LOOKS = ["글자", "별", "달", "고양이", "행성"] as const;
export type KeeperLook = (typeof KEEPER_LOOKS)[number];
export const KEEPER_SVG: Record<Exclude<KeeperLook, "글자">, string> = { 별: "star", 달: "moon", 고양이: "cat", 행성: "planet" };
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

// 일기에서 찾은 것으로 우주 넓히기(WS25): 이 기록에서 우주에 처음 나온 해 · 작은 별 · 사람(먼저 쓴 기록 순서로 가장 앞이 이 기록).
export function grewFrom(d: Pick<Universe, "suns" | "stars" | "planets" | "people">, id: string) {
  const at = new Map(d.planets.map((p) => [p.id, p.written_at + p.id]));
  if (!at.has(id)) return { suns: [], stars: [], people: [] };
  const first = (ids: string[]) => ids.reduce((a, b) => ((at.get(b) ?? "~") < (at.get(a) ?? "~") ? b : a), ids[0]);
  const by = (k: "sun_id" | "star_id", x: string) => d.planets.filter((p) => p[k] === x).map((p) => p.id);
  return {
    suns: d.suns.filter((s) => first(by("sun_id", s.id)) === id).map((s) => s.name),
    stars: d.stars.filter((s) => first(by("star_id", s.id)) === id).map((s) => s.name),
    people: d.people.filter((p) => p.planets.includes(id) && first(p.planets) === id).map((p) => p.name),
  };
}
