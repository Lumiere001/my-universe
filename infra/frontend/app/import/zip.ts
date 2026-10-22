// 인스타그램 '내 정보 다운로드' ZIP 에서 posts_N.json 만 꺼낸다(사진 · 영상은 읽지 않음). 라이브러리 없이 브라우저 DecompressionStream.
// 큰 ZIP(수 GB, ZIP64)도 끝의 목차와 그 파일 자리만 잘라 읽는다. posts_1.json 을 바로 골라도 된다(휴대폰이 ZIP 을 풀어 둔 경우).
// 깨진 한글 복원 · 이어 쓴 게시물 묶기는 서버(app/service/importer)가 한다. 여기서는 캡션 · 시각만 남겨 보낸다.

export type RawPost = { title: string; creation_timestamp: number | null; media: { title: string; creation_timestamp: number | null }[] };
type Post = { title?: string; creation_timestamp?: number; media?: { title?: string; creation_timestamp?: number }[] };

const NOT_FOUND = "이 파일에서 게시물(posts_1.json)을 찾지 못했어요. 인스타그램 '내 정보 다운로드'를 JSON 형식으로 받았는지, " +
  "여러 ZIP으로 나뉘었다면 다른 ZIP을 골라 보세요.";
const POSTS = /(^|\/)posts_\d+\.json$/;

async function bytes(f: Blob, from: number, to: number): Promise<DataView> {
  return new DataView(await f.slice(from, to).arrayBuffer());
}
const u64 = (v: DataView, at: number) => Number(v.getBigUint64(at, true));

async function unzipPosts(f: Blob): Promise<string[]> {
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
  const cd = await bytes(f, off, off + size), out: string[] = [];
  for (let p = 0; p + 46 <= cd.byteLength && cd.getUint32(p, true) === 0x02014b50;) {
    const method = cd.getUint16(p + 10, true), nlen = cd.getUint16(p + 28, true), xlen = cd.getUint16(p + 30, true);
    let csize = cd.getUint32(p + 20, true), at = cd.getUint32(p + 42, true);
    const name = new TextDecoder().decode(new Uint8Array(cd.buffer, cd.byteOffset + p + 46, nlen));
    // ZIP64 덧붙임 칸(0x0001): 0xffffffff 인 값만 원래 크기 → 압축 크기 → 위치 순서로 8바이트씩
    for (let x = p + 46 + nlen; x + 4 <= p + 46 + nlen + xlen; x += 4 + cd.getUint16(x + 2, true)) {
      if (cd.getUint16(x, true) !== 1) continue;
      let k = x + 4;
      if (cd.getUint32(p + 24, true) === 0xffffffff) k += 8;
      if (csize === 0xffffffff) { csize = u64(cd, k); k += 8; }
      if (at === 0xffffffff) at = u64(cd, k);
    }
    p += 46 + nlen + xlen + cd.getUint16(p + 32, true);
    if (!POSTS.test(name) || name.startsWith("__MACOSX/")) continue;
    const lh = await bytes(f, at, at + 30), start = at + 30 + lh.getUint16(26, true) + lh.getUint16(28, true);
    const raw = f.slice(start, start + csize);
    if (method === 0) out.push(await raw.text());
    else if (method === 8) out.push(await new Response(raw.stream().pipeThrough(new DecompressionStream("deflate-raw"))).text());
    else throw new Error("이 ZIP의 압축 방식은 읽지 못해요. 인스타그램에서 받은 파일 그대로 골라 주세요.");
  }
  return out;
}

// 고른 파일 → 게시물(캡션 · 시각만). ZIP 이면 posts_N.json 을 모두, JSON 이면 그 파일 하나.
export async function readPosts(f: File): Promise<RawPost[]> {
  const files = /\.json$/i.test(f.name) ? [await f.text()] : await unzipPosts(f);
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
