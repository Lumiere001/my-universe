// 조사 붙이기: 앞말 끝 글자의 받침으로 을/를 · 이/가 · 은/는 · 과/와 · 으로/로를 고른다('을(를)' 대신).
// 한글이 아닌 끝 글자(영어 이름 · 숫자)는 받침을 알 수 없어 두 꼴을 함께 적는다.
type Pair = "을/를" | "이/가" | "은/는" | "과/와" | "으로/로";

export function particle(word: string, pair: Pair): string {
  const [a, b] = pair.split("/");
  const c = word.charCodeAt(word.length - 1) - 0xac00;
  if (!(c >= 0 && c <= 11171)) return `${a}(${b})`;
  const end = c % 28;   // 0 = 받침 없음, 8 = ㄹ
  return end === 0 || (pair === "으로/로" && end === 8) ? b : a;
}

export const josa = (word: string, pair: Pair) => word + particle(word, pair);
