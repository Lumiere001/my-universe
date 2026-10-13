"use client";
// 별지기 이름(설정 keeper_name). 말풍선 이름표 · 동그라미 글자에 쓴다. LLM 에는 보내지 않는다.
import { useEffect, useState } from "react";
import { getMe } from "@/lib/api";

export const KEEPER = "별지기";
let cached: Promise<string> | null = null;
// ponytail: 탭 안에서 /me 를 한 번만 읽는다. 다른 계정으로 바꾸면 새로고침 뒤에 맞는다.
export function useKeeperName() {
  const [n, setN] = useState(KEEPER);
  useEffect(() => {
    (cached ??= getMe().then((m) => m.settings.keeper_name || KEEPER, () => { cached = null; return KEEPER; })).then(setN);
  }, []);
  return n;
}
export const rememberKeeperName = (n: string) => { cached = Promise.resolve(n); };

// 설정: 별지기 이름 바꾸기(1~12자)
export function KeeperNameField({ value, onSave }: { value: string; onSave: (n: string) => void }) {
  const [v, setV] = useState(value);
  const n = v.trim();
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); if (n) onSave(n); }}>
      <div style={{ flex: "1 1 160px" }}>
        <label htmlFor="keeper">별지기 이름</label>
        <input id="keeper" value={v} maxLength={12} onChange={(e) => setV(e.target.value)} placeholder={KEEPER} />
      </div>
      <button type="submit" className="small" style={{ alignSelf: "flex-end" }} disabled={!n || n === value}>이름 바꾸기</button>
    </form>
  );
}
