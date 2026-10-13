"use client";
// 별지기 이름(설정 keeper_name) · 모습(keeper_look, 꾸미기 WS25). 말풍선 이름표 · 동그라미에 쓴다. LLM 에는 보내지 않는다.
// 모습은 <html data-keeper> + CSS 변수 --keeper 로 모든 .voice .who 에 한 번에 입힌다('글자' = 지금처럼 이름 첫 글자).
import { useEffect, useState } from "react";
import { getMe, type Settings } from "@/lib/api";
import { KEEPER_SVG } from "./universeLook";

export const KEEPER = "별지기";
let cached: Promise<Settings | null> | null = null;
// ponytail: 탭 안에서 /me 를 한 번만 읽는다. 다른 계정으로 바꾸면 새로고침 뒤에 맞는다.
const load = () => (cached ??= getMe().then((m) => { showKeeperLook(m.settings.keeper_look); return m.settings; },
  () => { cached = null; return null; }));

export function showKeeperLook(look?: string | null) {
  const file = KEEPER_SVG[look as keyof typeof KEEPER_SVG], h = document.documentElement;
  if (file) { h.dataset.keeper = file; h.style.setProperty("--keeper", `url(/keeper/${file}.svg)`); }
  else { delete h.dataset.keeper; h.style.removeProperty("--keeper"); }
}

export function useKeeperName() {
  const [n, setN] = useState(KEEPER);
  useEffect(() => { load().then((s) => setN(s?.keeper_name || KEEPER)); }, []);
  return n;
}
// 로그인 뒤 Shell 이 한 번 그린다: 어느 화면으로 들어와도 별지기 모습이 맞게
export function KeeperLook() { useKeeperName(); return null; }
export const rememberSettings = (s: Settings) => { cached = Promise.resolve(s); showKeeperLook(s.keeper_look); };

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
