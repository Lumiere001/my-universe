// 지난 일기 가져오기에서 고른 파일 읽기. 라이브러리 없이 브라우저 DecompressionStream 으로 ZIP 을 푼다.
// 인스타그램 '내 정보 다운로드' ZIP 에서는 posts_N.json 만 꺼낸다(사진 · 영상은 읽지 않음). 큰 ZIP(수 GB, ZIP64)도 끝의 목차와
// 그 파일 자리만 잘라 읽는다. posts_1.json 을 바로 골라도 된다(휴대폰이 ZIP 을 풀어 둔 경우).
// 깨진 한글 복원 · 이어 쓴 게시물 묶기는 서버(app/service/importer)가 한다. 여기서는 캡션 · 시각만 남겨 보낸다.
// 글 파일(.txt · .md, 2026-10-28): 파일 하나 = 일기 한 편. 여러 개를 고르거나 ZIP 으로 묶어 고른다. 윈도 메모장 파일은 UTF-8 · CP949 · UTF-16.

export type RawPost = { title: string; creation_timestamp: number | null; media: { title: string; creation_timestamp: number | null }[] };
type Post = { title?: string; creation_timestamp?: number; media?: { title?: string; creation_timestamp?: number }[] };

const NOT_FOUND = "이 파일에서 게시물(posts_1.json)을 찾지 못했어요. 인스타그램 '내 정보 다운로드'를 JSON 형식으로 받았는지, " +
  "여러 ZIP으로 나뉘었다면 다른 ZIP을 골라 보세요.";
const POSTS = /(^|\/)posts_\d+\.json$/;
const TEXT = /\.(txt|md)$/i;

async function bytes(f: Blob, from: number, to: number): Promise<DataView> {
  return new DataView(await f.slice(from, to).arrayBuffer());
}
const u64 = (v: DataView, at: number) => Number(v.getBigUint64(at, true));

// 글자 판 맞추기: UTF-16(BOM) → UTF-8(BOM 있든 없든, 틀린 바이트가 있으면 아님) → CP949(윈도 메모장 'ANSI')
export function decode(b: Uint8Array): string {
  if (b[0] === 0xff && b[1] === 0xfe) return new TextDecoder("utf-16le").decode(b);
  if (b[0] === 0xfe && b[1] === 0xff) return new TextDecoder("utf-16be").decode(b);
  try { return new TextDecoder("utf-8", { fatal: true }).decode(b); } catch { return new TextDecoder("euc-kr").decode(b); }
}

type Entry = { name: string; data: Blob; modified: number };

// ZIP 목차에서 want(이름)인 파일만 꺼낸다. 이름은 UTF-8 표시가 없으면 윈도 압축(CP949)일 수 있어 decode 로 읽는다.
async function unzip(f: Blob, want: (name: string) => boolean): Promise<Entry[]> {
  const tailFrom = Math.max(0, f.size - 65_557), tail = await bytes(f, tailFrom, f.size);
  let e = tail.byteLength - 22;
  while (e >= 0 && tail.getUint32(e, true) !== 0x06054b50) e--;   // 목차 끝 표시
  if (e < 0) throw new Error("ZIP 파일을 읽지 못했어요. 받은 파일 그대로 골라 주세요.");
  let size = tail.getUint32(e + 12, true), off = tail.getUint32(e + 16, true);
  if (off === 0xffffffff || size === 0xffffffff) {   // ZIP64(4GB 넘는 ZIP): 목차 위치는 ZIP64 끝 표시에
    const loc = await bytes(f, tailFrom + e - 20, tailFrom + e);
    const z = await bytes(f, u64(loc, 8), u64(loc, 8) + 56);
    size = u64(z, 40); off = u64(z, 48);
  }
  const cd = await bytes(f, off, off + size), out: Entry[] = [];
  for (let p = 0; p + 46 <= cd.byteLength && cd.getUint32(p, true) === 0x02014b50;) {
    const flags = cd.getUint16(p + 8, true), method = cd.getUint16(p + 10, true);
    const time = cd.getUint16(p + 12, true), date = cd.getUint16(p + 14, true);
    const nlen = cd.getUint16(p + 28, true), xlen = cd.getUint16(p + 30, true);
    let csize = cd.getUint32(p + 20, true), at = cd.getUint32(p + 42, true);
    const raw = new Uint8Array(cd.buffer, cd.byteOffset + p + 46, nlen);
    const name = flags & 0x800 ? new TextDecoder().decode(raw) : decode(raw);
    // ZIP64 덧붙임 칸(0x0001): 0xffffffff 인 값만 원래 크기 → 압축 크기 → 위치 순서로 8바이트씩
    for (let x = p + 46 + nlen; x + 4 <= p + 46 + nlen + xlen; x += 4 + cd.getUint16(x + 2, true)) {
      if (cd.getUint16(x, true) !== 1) continue;
      let k = x + 4;
      if (cd.getUint32(p + 24, true) === 0xffffffff) k += 8;
      if (csize === 0xffffffff) { csize = u64(cd, k); k += 8; }
      if (at === 0xffffffff) at = u64(cd, k);
    }
    p += 46 + nlen + xlen + cd.getUint16(p + 32, true);
    if (!want(name) || name.startsWith("__MACOSX/") || /(^|\/)\._/.test(name)) continue;   // 맥이 덧붙인 숨은 파일은 뺌
    const lh = await bytes(f, at, at + 30), start = at + 30 + lh.getUint16(26, true) + lh.getUint16(28, true);
    const body = f.slice(start, start + csize);
    // 목차의 고친 시각(DOS 형식, 이 기기 시간대) → 파일을 저장한 때
    const modified = new Date(1980 + (date >> 9), ((date >> 5) & 15) - 1, date & 31, time >> 11, (time >> 5) & 63, (time & 31) * 2).getTime();
    if (method === 0) out.push({ name, data: body, modified });
    else if (method === 8) out.push({ name, data: await new Response(body.stream().pipeThrough(new DecompressionStream("deflate-raw"))).blob(), modified });
    else throw new Error("이 ZIP의 압축 방식은 읽지 못해요. 받은 파일 그대로 골라 주세요.");
  }
  return out;
}

// 고른 파일 → 게시물(캡션 · 시각만). ZIP 이면 posts_N.json 을 모두, JSON 이면 그 파일 하나.
export async function readPosts(f: File): Promise<RawPost[]> {
  const files = /\.json$/i.test(f.name) ? [await f.text()] : await Promise.all((await unzip(f, (n) => POSTS.test(n))).map((x) => x.data.text()));
  if (!files.length) throw new Error(NOT_FOUND);
  const posts: Post[] = files.flatMap((t) => {
    const j = JSON.parse(t);
    if (!Array.isArray(j)) throw new Error(NOT_FOUND);
    return j;
  });
  return posts.map((p) => {
    const m = p.media?.[0] ?? {};
    return { title: p.title ?? "", creation_timestamp: p.creation_timestamp ?? null,
      media: [{ title: m.title ?? "", creation_timestamp: m.creation_timestamp ?? null }] };
  });
}

// 고른 파일들(.txt · .md 여러 개, 또는 그런 파일을 묶은 ZIP) → 글 파일 목록. skipped = 글 파일이 아니라 뺀 수.
export type TextFile = { name: string; raw: string; modified: number };
export async function readTextFiles(picked: File[]): Promise<{ files: TextFile[]; skipped: number }> {
  const files: TextFile[] = [];
  let skipped = 0;
  for (const f of picked) {
    if (TEXT.test(f.name)) files.push({ name: f.name, raw: decode(new Uint8Array(await f.arrayBuffer())), modified: f.lastModified });
    else if (/\.zip$/i.test(f.name)) {
      const inside = await unzip(f, (n) => TEXT.test(n));
      if (!inside.length) throw new Error("이 ZIP에서 글 파일(.txt · .md)을 찾지 못했어요. 인스타그램에서 받은 ZIP이면 '인스타그램 ZIP'을 골라 주세요.");
      for (const x of inside) files.push({ name: x.name, raw: decode(new Uint8Array(await x.data.arrayBuffer())), modified: x.modified });
    } else skipped++;
  }
  if (!files.length) throw new Error(".txt · .md 파일을 찾지 못했어요. 메모장에 쓴 글은 .txt 파일이에요.");
  return { files, skipped };
}

// 이 기기 시간대의 날(YYYY-MM-DD)
export const localDay = (t: Date) => new Date(t.getTime() - t.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);

// 제목(짧은 첫 줄) 속 날짜 → YYYY-MM-DD. 서버 rules/dates.py 의 흔한 모양만: 2026-10-03 · 2026년 10월 3일 · 10/3 · 10월 3일.
// 연도가 없으면 저장한 날과 같거나 앞선 가장 가까운 해. 차례 · 보이기용이고, 글이 다루는 날은 서버가 다시 읽는다.
export function titleDay(title: string, saved: Date): string {
  const iso = (y: number, m: number, d: number) => {
    const t = new Date(Date.UTC(y, m - 1, d));
    return t.getUTCMonth() === m - 1 && t.getUTCDate() === d ? t.toISOString().slice(0, 10) : "";
  };
  const ymd = /(?<!\d)(\d{4})\s*(?:[-./]|년)\s*(\d{1,2})\s*(?:[-./]|월)\s*(\d{1,2})(?!\d)/.exec(title);
  if (ymd) return iso(+ymd[1], +ymd[2], +ymd[3]);
  const md = /(?<![\d.])(\d{1,2})\s*(?:\/|월\s*)(\d{1,2})(?!\d)/.exec(title);
  if (!md) return "";
  const y = saved.getFullYear(), here = iso(y, +md[1], +md[2]);
  return here && here <= localDay(saved) ? here : iso(y - 1, +md[1], +md[2]);
}

// 미리 보기 요청을 나눈다(배포 서버의 요청 · 응답 크기 한도 4.5MB). 이어 쓴 게시물(하루 안)을 가르지 않게 하루 넘게 떨어진 곳에서만 자른다.
// ponytail: 몇 달 동안 하루도 빠짐없이 올린 계정이면 한 덩어리가 커질 수 있음. 그런 사용자가 나오면 크기로도 자름
export function chunks(posts: RawPost[], size = 200): RawPost[][] {
  const ts = (p: RawPost) => p.creation_timestamp ?? p.media[0]?.creation_timestamp ?? 0;
  const out: RawPost[][] = [];
  let cur: RawPost[] = [];
  for (const p of [...posts].sort((a, b) => ts(a) - ts(b))) {
    if (cur.length >= size && ts(p) - ts(cur[cur.length - 1]) >= 86_400) { out.push(cur); cur = []; }
    cur.push(p);
  }
  return cur.length ? [...out, cur] : out;
}
