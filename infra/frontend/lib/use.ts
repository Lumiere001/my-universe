"use client";
import { useCallback, useEffect, useState } from "react";
import { getOntology, why, type Ontology } from "./api";

// 데이터 하나를 불러오는 작은 훅. [값, 오류 문장, 다시 불러오기]. fail: 서버가 이유를 주지 않았을 때 그 화면의 문장
export function useLoad<T>(fn: () => Promise<T>, fail = "불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요."): [T | null, string, () => void] {
  const [v, setV] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    fn().then((x) => { setV(x); setErr(""); }, (e) => setErr(why(e, fail)));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  return [v, err, load];
}

let onto: Promise<Ontology> | null = null;
export const useOntology = () => useLoad(() => (onto ??= getOntology()))[0];

// 생각 종류의 보이는 이름(예: 자기평가(부정) → 아쉬웠던 점). 온톨로지에 display 가 있으면 그것을 쓴다.
export function useKindName() {
  const onto = useOntology();
  return (k: string) => (onto?.kinds.find((x) => x.name === k) as { display?: string } | undefined)?.display ?? k;
}
