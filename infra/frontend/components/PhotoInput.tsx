"use client";
// 사진(손글씨 · 일기장) 글자 읽기(WS18): 사진 여러 장(쪽 순서 바꾸기 · 빼기) → 화면에서 줄여(긴 변 2400px JPEG, 4MB 아래 ·
// 위치 정보 같은 메타데이터도 빠짐) 한 장씩 POST /photo/read → 읽은 글을 쪽 순서대로 이어 쓰기 칸에 채움 → 사용자가 고친 뒤
// '우주에 띄우기'(source=사진). 사진은 서버에 저장하지 않고, 읽고 나면 화면에서도 비운다.
import { useEffect, useRef, useState } from "react";
import { ApiError, readPhoto, why } from "@/lib/api";

const LIMIT = 4_000_000;   // 서버 한도 4.5MB(Vercel 요청 본문) 아래로
const LONG_SIDE = 2400;    // 글자 읽기에 넉넉한 긴 변(px)
const MAX_TEXT = 8000;     // 백엔드 MAX_TEXT_CHARS 기본값
const OK_TYPE = /^image\/(jpeg|png|heic|heif)$/i, OK_NAME = /\.(jpe?g|png|heic|heif)$/i;
const isHeic = (f: File) => /heic|heif/i.test(f.type) || /\.(heic|heif)$/i.test(f.name);

type Page = { id: number; file: File; url: string };

// 브라우저가 그릴 수 있으면 다시 그려 JPEG 로(크면 조금씩 더 줄임). 크롬은 HEIC 를 못 그려서, 4MB 아래 HEIC 는 그대로 보낸다(서버 · Upstage 가 읽음).
export async function shrink(file: File): Promise<Blob> {
  let bmp: ImageBitmap;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });   // 폰 사진의 회전 정보(EXIF)대로 세워 그림
  } catch {
    if (isHeic(file) && file.size <= LIMIT) return file;
    throw new Error(isHeic(file)
      ? "이 HEIC 사진은 커서 브라우저에서 줄이지 못해요. 아이폰 설정 › 카메라 › 포맷 › ‘높은 호환성’으로 찍거나 JPG로 바꿔 올려 주세요."
      : "이 사진을 열지 못했어요. 다른 사진으로 해 주세요.");
  }
  try {
    for (let side = LONG_SIDE, q = 0.85; side >= 800; side = Math.round(side * 0.8), q = Math.max(0.6, q - 0.1)) {
      const k = Math.min(1, side / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
      const g = c.getContext("2d")!;
      g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);   // 투명한 PNG 가 검게 나오지 않게
      g.drawImage(bmp, 0, 0, c.width, c.height);
      const blob = await new Promise<Blob | null>((ok) => c.toBlob(ok, "image/jpeg", q));
      if (blob && blob.size <= LIMIT) return blob;
    }
  } finally {
    bmp.close();
  }
  throw new Error("사진을 충분히 줄이지 못했어요. 다른 사진으로 해 주세요.");
}

export default function PhotoInput({ onRead, disabled }: { onRead: (text: string) => void; disabled?: boolean }) {
  const [pages, setPages] = useState<Page[]>([]);
  const [busy, setBusy] = useState("");   // "1/2쪽 읽는 중…"
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const seq = useRef(0);
  const urls = useRef<string[]>([]);
  useEffect(() => () => urls.current.forEach(URL.revokeObjectURL), []);   // 화면을 떠나면 미리보기도 비움

  const drop = (keep: (p: Page) => boolean) => setPages((ps) => {
    ps.filter((p) => !keep(p)).forEach((p) => URL.revokeObjectURL(p.url));
    return ps.filter(keep);
  });
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = [...(e.target.files ?? [])];
    e.target.value = "";   // 같은 사진을 다시 골라도 다시 받게
    setErr(""); setNote("");
    const bad = files.filter((f) => !OK_TYPE.test(f.type) && !OK_NAME.test(f.name));
    if (bad.length) setErr(`jpg · png · heic 사진만 읽을 수 있어요. (‘${bad[0].name}’은 빼 두었어요)`);
    const add = files.filter((f) => !bad.includes(f)).map((file) => {
      const url = URL.createObjectURL(file);
      urls.current.push(url);
      return { id: ++seq.current, file, url };
    });
    setPages((ps) => [...ps, ...add]);
  };
  const move = (i: number, d: -1 | 1) => setPages((ps) => {
    const n = [...ps];
    [n[i], n[i + d]] = [n[i + d], n[i]];
    return n;
  });
  const read = async () => {
    setErr(""); setNote("");
    const texts: string[] = [];
    try {
      for (const [i, p] of pages.entries()) {
        setBusy(`${i + 1}/${pages.length}쪽 읽는 중…`);
        texts.push((await readPhoto(await shrink(p.file))).text.trim());
      }
    } catch (e) {
      setErr(e instanceof ApiError && e.code === "network" ? "서버에 닿지 못했어요. 잠시 뒤 다시 눌러 주세요." : why(e, "사진의 글자를 읽지 못했어요. 잠시 뒤 다시 해 주세요."));
      return;
    } finally {
      setBusy("");
    }
    const text = texts.filter(Boolean).join("\n");
    if (!text) return setErr("사진에서 글자를 찾지 못했어요. 밝은 곳에서 글씨가 크게 나오게 다시 찍어 주세요.");
    const empty = texts.map((t, i) => (t ? 0 : i + 1)).filter(Boolean);
    drop(() => false);   // 다 읽은 사진은 화면에서도 비운다
    onRead(text);
    setNote(`${texts.length}쪽을 읽어 글 칸에 채웠어요. 잘못 읽은 글자를 고친 뒤 띄워 주세요.`
      + (empty.length ? ` (${empty.join(", ")}쪽에서는 글자를 찾지 못했어요)` : "")
      + (text.length > MAX_TEXT ? ` 글이 ${MAX_TEXT.toLocaleString()}자를 넘어요. 나눠서 띄워 주세요.` : ""));
  };

  const off = disabled || !!busy;
  return (
    <div className="stack" aria-label="사진으로 쓰기" role="group">
      <div>
        <label htmlFor="photo">손글씨 일기장 사진에서 글자 읽기 (여러 쪽이면 여러 장 골라 주세요)</label>
        <input id="photo" type="file" multiple accept="image/jpeg,image/png,image/heic,image/heif,.heic,.heif"
          disabled={off} onChange={pick} />
      </div>
      {pages.length > 0 && (
        <ol className="stack" aria-label="읽을 사진(쪽 순서)" style={{ margin: 0, paddingLeft: 22 }}>
          {pages.map((p, i) => (
            <li key={p.id}>
              <div className="row">
                {/* 크롬은 HEIC 미리보기를 못 그려서 이름만 보인다 */}
                <img src={p.url} alt="" width={44} height={58} style={{ objectFit: "cover", borderRadius: 6, background: "var(--line)" }} />
                <span className="sub" style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{p.file.name}</span>
                <button type="button" className="small" disabled={off || i === 0} onClick={() => move(i, -1)} aria-label={`${i + 1}쪽 앞으로`}>↑</button>
                <button type="button" className="small" disabled={off || i === pages.length - 1} onClick={() => move(i, 1)} aria-label={`${i + 1}쪽 뒤로`}>↓</button>
                <button type="button" className="small" disabled={off} onClick={() => drop((x) => x.id !== p.id)} aria-label={`${i + 1}쪽 빼기`}>빼기</button>
              </div>
            </li>
          ))}
        </ol>
      )}
      {pages.length > 0 && (
        <button type="button" disabled={off} onClick={read}>{busy || `사진 ${pages.length}장 글자 읽기`}</button>
      )}
      <p className="sub" style={{ margin: 0 }}>
        사진은 글자를 읽는 데만 쓰고 저장하지 않아요. 사진 속 이름은 가릴 수 없어 그대로 글자 읽기(Upstage)로 가요.
      </p>
      {note && <p className="toast" role="status" style={{ margin: 0 }}>{note}</p>}
      {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
    </div>
  );
}
