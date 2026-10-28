// API 층 하나. 모양은 docs/api-v8.md 를 따른다.
// NEXT_PUBLIC_MOCK=1 이면 같은 함수가 lib/mock.ts 의 고정 데이터(가상 인물 하늘)를 돌려준다.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1";
export const DEV_LOGIN = process.env.NEXT_PUBLIC_DEV_LOGIN === "1";
const BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8001").replace(/\/$/, "");

/* ---------- 타입 (docs/api-v8.md) ---------- */
export type Weather = "맑음" | "구름 조금" | "흐림" | "비" | "천둥" | "안개";
export type Tone = "다정하게" | "담백하게" | "고양이처럼" | "팩폭" | "직접 정하기";
export type Thought = {
  id: string; text: string; kind: string; grateful: boolean; certainty: string; value: string | null;
  quote: string; self_change: string | null; topic: string; star_id: string; sun_id: string; people: string[];
  other: string | null; state: { type: string; status: string; mistake: boolean } | null;
};
export type Relation = {
  id: string; from: string; to: string; from_entry: string; to_entry: string; type: string; group: string;
  line: "실선" | "점선"; cross_domain: boolean; needs_confirm: boolean; explanation: string; quote: string | null;
};
export type EntryResult = {
  // confirm = 대화 초안이 save 앞에서 멈춰 요약 확인을 기다림(WS20)
  id: string; status: "processing" | "done" | "failed" | "confirm"; step: string; written_at: string; title: string;
  weather: Weather | null; crisis: boolean;
  info: { summary: string; addressee: string; addressee_person: string | null; events: string[] } | null;
  thoughts: Thought[]; relations: Relation[];
  past: { thought_id: string; entry_id: string; text: string; written_at: string }[];
  reached: { aspiration_id: string; quote: string; message: string }[];
  message: { text: string; tone: Tone; mode: "normal" | "comfort"; check_in: string | null } | null;
  next_question: { kind: "weather" | "aspiration" | "free" | "none"; text: string } | null;
  people_questions: { id: string; name: string; question: string; options: string[] }[];
  // 기록 칸(WS11): 글이 다루는 날 · 확실/추정 · 날짜 확인 필요. duplicate = 이미 정리한 같은 글(그 기록의 결과)
  source?: string; day?: string; day_basis?: "확실" | "추정"; day_check?: boolean; duplicate?: boolean;
  confirmed?: "확인 전" | "확인됨" | null;
  // 관측 보고서(WS15): 관측 상태 · 한계. 끝난 기록에만
  observation?: { state: string; limits: string[] } | null;
};
export type Progress = { entry_id: string; step: string; label: string; done: number; total: number };
export type StreamError = { entry_id: string | null; code: string; message: string; resumable: boolean };
export type EntrySummary = {
  id: string; written_at: string; title: string; summary: string; weather: Weather | null;
  status: string; sun: string | null; star: string | null; day?: string; day_check?: boolean;
};
export type Universe = {
  suns: { id: string; name: string; custom: boolean; planet_count: number }[];
  stars: { id: string; sun_id: string; name: string; planet_count: number }[];
  planets: { id: string; star_id: string; sun_id: string; written_at: string; title: string; order: number;
    ring: boolean; people: string[]; weather: Weather | null;
    // 크기 = 생각 수, 밝기 = 확신, '?' = 열린 질문, 고리: 열림(빈 고리) · 채워짐(지킨 다짐)
    ring_state?: "열림" | "채워짐" | null; thought_count?: number; certainty?: string | null; has_question?: boolean }[];
  links: { id: string; from_planet: string; to_planet: string; type: string; line: "실선" | "점선";
    cross_domain: boolean; needs_confirm: boolean; explanation: string;
    ended?: boolean; from_quote?: string; to_quote?: string }[];  // ended: 끝난 목표 충돌, 인용: 그때 → 지금
  twins: { id: string; a_planet: string; b_planet: string; topic: string; status: string }[];
  blackholes: { id: string; star_id: string; label: string; size: number; planets: string[] }[];
  north_star: { text: string; values: string[]; reached_planets?: string[];
    reached?: { entry_id: string; quote: string; at: string }[] } | null;
  people: { id: string; name: string; relation: string; planets: string[] }[];
};
export type PersonThoughts = { person: { id: string; name: string; relation: string };
  thoughts: (Thought & { entry_id: string; written_at: string; title: string })[] };
export type Person = { id: string; name: string; nickname: string; relation: string; auto: boolean; planets: string[];
  forget_as?: string };   // 지우면 이름 자리에 들어갈 말(서버 pseudonym.forget_word: 엄마 → 부모 …)
export type Aspiration = {
  id: string; said: string; values: string[]; obstacle: string; if_then: string; said_at: string;
  reached: { entry_id: string; quote: string; at: string }[];
};
export type AspirationState = { current: Aspiration | null; history: Aspiration[]; ask: { should_ask: boolean; step: number } };
export type Settings = {
  tone: Tone; tone_note?: string; fact_bomb_ack: boolean; gentle_today: string | null; comfort_only_today: string | null;   // tone_note: 직접 정하기의 말투 바람(200자)
  suggestions: "적게" | "보통" | "많이"; cross_links: "숨김" | "눌렀을 때" | "항상"; weather_ask: boolean;
  keeper_name?: string;
  theme?: string; keeper_look?: string;   // 꾸미기(WS25): 우주 테마 · 별지기 모습(값 목록은 components/universeLook.ts)
};
export type Me = { user: { id: string; email: string }; settings: Settings;
  onboarding: { entries: number; aspiration: string; weather_asked: boolean } };
export type Feedback = { target: string; target_id?: string | null; value: string; text?: string };
export type Ontology = typeof import("./ontology.json");
export type DiaryInput = { text: string; title?: string; written_at?: string; weather?: Weather | null; day?: string; source_ref?: string;
  source?: "텍스트" | "사진" | "지난 글 묶음" | "대화" };   // 기록 출처(기본 텍스트). 사진에서 읽은 글이면 "사진"(WS18), 인스타 가져오기는 '지난 글 묶음' + source_ref + written_at(WS17)
// 쓰기 화면 위 별지기 말풍선(GET /diary/prompt)
export type Prompt = { kind: "first" | "weather" | "aspiration" | "free" | "none"; text: string;
  vow: { thought_id: string; text: string; overdue: boolean } | null };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

/* ---------- 로그인 (Supabase) ---------- */
let sb: SupabaseClient | null = null;
export function supabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL, key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return (sb ??= createClient(url, key));
}
async function token(): Promise<string | null> {
  const c = supabase();
  return c ? (await c.auth.getSession()).data.session?.access_token ?? null : null;
}

/* ---------- 요청 ---------- */
// 화면에 보일 공통 실패 문장(docs/content/C-01 상황별 안내)
export const NET = "서버에 닿지 못했어요. 인터넷 연결을 확인하고 다시 해 주세요.";
export const FAIL = "문제가 생겨 멈췄어요. 잠시 뒤 다시 해 주세요.";
const INPUT = "넣은 내용을 다시 확인해 주세요.";
// 서버가 준 이유. 영문 칸 이름이 붙은 입력 거절(옛 서버)은 C-01 문장으로, 이유 없는 실패(internal · JSON 아님)는 "" → 화면이 고른 문장
const reason = (code: string, msg?: string) =>
  msg?.startsWith("입력을 확인해 주세요") ? INPUT : code === "internal" ? "" : msg ?? "";
// 오류 → 화면 문장: 서버가 준 한국어 이유가 있으면 그것, 없으면 그 자리의 문장(영어 브라우저 오류 'Failed to fetch' 등은 보이지 않음)
export const why = (e: unknown, fallback = FAIL) => {
  const m = (e as { message?: string } | null)?.message ?? "";
  return /[가-힣]/.test(m) ? m : fallback;
};

// 요청 하나. 닿지 못하면 ApiError(0, "network", NET), 거절되면 서버 코드 · 이유를 담은 ApiError
async function send(path: string, init: RequestInit): Promise<Response> {
  const t = await token();
  let res: Response;
  try {
    res = await fetch(BASE + path, { ...init, headers: { ...init.headers, ...(t && { Authorization: `Bearer ${t}` }) } });
  } catch {
    throw new ApiError(0, "network", NET);
  }
  if (!res.ok) {
    const j = await res.json().catch(() => null);   // 배포 앞단이 막은 413 등은 JSON 이 아니다
    const code = j?.error?.code ?? "http_" + res.status;
    throw new ApiError(res.status, code, reason(code, j?.error?.message));
  }
  return res;
}
const req = (method: string, path: string, body?: unknown) => send(path, {
  method, headers: body === undefined ? {} : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
});
// SSE 를 여는 POST. 닿지 못하거나 거절되면 StreamError 로 던진다(net: 닿지 못했을 때 그 화면의 문장)
async function postStream(path: string, body: unknown, net: string): Promise<Response> {
  try {
    return await send(path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (e) {
    const x = e as ApiError;
    throw { entry_id: null, code: x.code, message: x.code === "network" ? net : x.message, resumable: false } as StreamError;
  }
}
const json = async <T,>(method: string, path: string, body?: unknown): Promise<T> => {
  const r = await req(method, path, body);
  return (r.status === 204 ? null : await r.json()) as T;
};
const mock = () => import("./mock");

/* ---------- SSE 읽기 ---------- */
export type StreamHandlers = { onProgress: (p: Progress) => void };

// "event: x\ndata: {...}\n\n" 덩어리를 하나씩 꺼낸다. ":" 로 시작하는 줄(keep-alive)은 무시한다.
export function parseSSE(buf: string): { events: { event: string; data: string }[]; rest: string } {
  const parts = buf.replace(/\r\n/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  const events = [];
  for (const block of parts) {
    let event = "message", data = "";
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const i = line.indexOf(":"), k = i < 0 ? line : line.slice(0, i), v = i < 0 ? "" : line.slice(i + 1).replace(/^ /, "");
      if (k === "event") event = v;
      else if (k === "data") data += (data ? "\n" : "") + v;
    }
    if (data) events.push({ event, data });
  }
  return { events, rest };
}

// 스트림을 끝까지 읽어 EntryResult 를 돌려준다. error 이벤트나 끊김은 StreamError 로 던진다.
async function readStream(res: Response, h: StreamHandlers): Promise<EntryResult> {
  const reader = res.body!.getReader(), dec = new TextDecoder();
  let buf = "", entryId: string | null = null;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      const p = parseSSE(buf + dec.decode(value, { stream: true }));
      buf = p.rest;
      for (const e of p.events) {
        const d = JSON.parse(e.data);
        if (e.event === "progress") { entryId = d.entry_id; h.onProgress(d); }
        else if (e.event === "result") return d as EntryResult;
        else if (e.event === "error") throw { ...d, entry_id: d.entry_id ?? entryId } as StreamError;
      }
    }
  } catch (e) {
    if ((e as StreamError).code) throw e;
    // 네트워크 끊김: 아래에서 이어서 하기로 처리
  }
  throw { entry_id: entryId, code: "disconnected", message: "연결이 끊겼어요.", resumable: !!entryId } as StreamError;
}

/* ---------- 일기 ---------- */
// 기록이 생기거나 바뀌면 사이드바 '지난 기록'(components/Shell.tsx)이 다시 읽는다
const changed = <T,>(x: T): T => { window.dispatchEvent(new Event("entries")); return x; };
export async function writeDiary(input: DiaryInput, h: StreamHandlers): Promise<EntryResult> {
  if (MOCK) return changed(await (await mock()).writeDiary(input, h));
  return changed(await readStream(await postStream("/diary/stream", input, "서버에 닿지 못했어요. 인터넷 연결을 확인해 주세요."), h));
}
export async function resumeDiary(id: string, h: StreamHandlers): Promise<EntryResult> {
  if (MOCK) return changed(await (await mock()).resumeDiary(id, h));
  return changed(await readStream(await req("POST", `/diary/${encodeURIComponent(id)}/resume/stream`), h));
}
export async function getDiary(id: string): Promise<EntryResult> {
  return MOCK ? (await mock()).getDiary(id) : json("GET", `/diary/${encodeURIComponent(id)}`);
}
export async function getPrompt(): Promise<Prompt> {
  return MOCK ? (await mock()).getPrompt() : json("GET", "/diary/prompt");
}
export async function setEntryDay(id: string, day: string): Promise<EntryResult> {
  return changed(MOCK ? await (await mock()).setEntryDay(id, day) : await json<EntryResult>("PATCH", `/diary/${encodeURIComponent(id)}/day`, { day }));
}
export async function deleteDiary(id: string): Promise<void> {
  if (MOCK) return changed(await (await mock()).deleteDiary(id));
  changed(await json("DELETE", `/diary/${encodeURIComponent(id)}`));
}
// JSON 내려받기(WS15, docs/api-v8.md §2.1): id 가 있으면 기록 하나, 없으면 전체. 다른 사람 이름은 가리지 않는다.
export async function exportDiary(id?: string): Promise<unknown> {
  if (MOCK) return { schema: "my-universe-export/1", exported_at: new Date().toISOString(), scope: id ? "entry" : "all",
    records: id ? [await getDiary(id)] : [], domains: [] };
  return json("GET", id ? `/export/${encodeURIComponent(id)}` : "/export");
}
export async function listDiary(before?: string): Promise<{ entries: EntrySummary[] }> {
  if (MOCK) return (await mock()).listDiary();
  return json("GET", `/diary?limit=20${before ? "&before=" + encodeURIComponent(before) : ""}`);
}

/* ---------- 우주 · 온톨로지 ---------- */
export async function getUniverse(): Promise<Universe> {
  return MOCK ? (await mock()).getUniverse() : json("GET", "/universe");
}
export async function getOntology(): Promise<Ontology> {
  return MOCK ? (await import("./ontology.json")).default : json("GET", "/ontology");
}

/* ---------- 피드백 ---------- */
export async function sendFeedback(f: Feedback): Promise<{ ok: boolean; state: unknown }> {
  return MOCK ? (await mock()).sendFeedback(f) : json("POST", "/feedback", f);
}

/* ---------- 사람 ---------- */
export async function listPeople(): Promise<{ people: Person[] }> {
  return MOCK ? (await mock()).listPeople() : json("GET", "/people");
}
export async function addPerson(p: { name: string; nickname: string; relation: string }): Promise<Person> {
  return MOCK ? (await mock()).addPerson(p) : json("POST", "/people", p);
}
export async function updatePerson(id: string, p: Partial<Person>): Promise<Person> {
  return MOCK ? (await mock()).updatePerson(id, p) : json("PATCH", `/people/${encodeURIComponent(id)}`, p);
}
export async function deletePerson(id: string): Promise<{ ok: boolean; replaced: number }> {
  return MOCK ? (await mock()).deletePerson(id) : json("DELETE", `/people/${encodeURIComponent(id)}`);
}
// 그 사람과 얽힌 생각(먼저 쓴 기록부터)
export async function getPersonThoughts(id: string): Promise<PersonThoughts> {
  return MOCK ? (await mock()).getPersonThoughts(id) : json("GET", `/people/${encodeURIComponent(id)}/thoughts`);
}
export async function answerPersonQuestion(id: string, answer: string): Promise<{ ok: boolean }> {
  return MOCK ? { ok: true } : json("POST", `/people/questions/${encodeURIComponent(id)}`, { answer });
}

/* ---------- 되고 싶은 모습 ---------- */
export async function getAspiration(): Promise<AspirationState> {
  return MOCK ? (await mock()).getAspiration() : json("GET", "/aspiration");
}
export async function saveAspiration(a: { now: string; want: string; obstacle: string; if_then: string; values: string[] }): Promise<Aspiration> {
  return MOCK ? (await mock()).saveAspiration(a) : json("POST", "/aspiration", a);
}
export async function declineAspiration(mode: "skip" | "stop"): Promise<{ ok: boolean }> {
  return MOCK ? { ok: true } : json("POST", "/aspiration/decline", { mode });
}

/* ---------- 나 · 설정 ---------- */
export async function getMe(): Promise<Me> {
  return MOCK ? (await mock()).getMe() : json("GET", "/me");
}
export async function patchSettings(s: Partial<Settings>): Promise<Settings> {
  return MOCK ? (await mock()).patchSettings(s) : json("PATCH", "/settings", s);
}
// 계정과 모든 기록 지우기(되돌릴 수 없음). 끝나면 화면이 로그아웃한다.
export async function deleteMe(): Promise<void> {
  if (!MOCK) await json("DELETE", "/me");
}

/* ---------- 동의 (WS24, docs/api-v8.md §6.1) ---------- */
export type Consent = { version: string; needed: boolean; agreed: { version: string; operator_read: boolean; at: string } | null };
export type ConsentInput = { version: string; required: boolean; sensitive: boolean; age14: boolean; operator_read: boolean };
export async function getConsent(): Promise<Consent> {
  return MOCK ? (await mock()).getConsent() : json("GET", "/consent");
}
export async function saveConsent(c: ConsentInput): Promise<Consent> {
  return MOCK ? (await mock()).saveConsent(c) : json("POST", "/consent", c);
}

/* ---------- 대화 · 요약 확인 (WS19 · WS20, docs/api-v8.md §8) ---------- */
export type TalkTurn = {
  role: "keeper" | "user"; text: string; at: string;
  kind?: string; mode?: "normal" | "comfort"; tone?: Tone; check_in?: string | null; via?: "text" | "voice";
};
export type Conversation = {
  id: string; created_at: string; updated_at: string; turns: TalkTurn[]; summary: string;
  from_entry: string | null; entry_id: string | null; turn_count: number; wrap: boolean;
};
export type TalkProgress = { conversation_id: string; step: string; label: string };
export type ConfirmInput = { summary?: string; fixes: { id: string; kind?: string; remove?: boolean }[]; agreed: string[] };

const TALK_NET = "서버에 닿지 못했어요. 말은 화면에 그대로 있어요. 인터넷 연결을 확인하고 다시 보내 주세요.";
export async function listTalks(): Promise<{ conversations: Conversation[] }> {
  return MOCK ? (await mock()).listTalks() : json("GET", "/talk");
}
// 새 대화(별지기가 먼저 묻는 첫 말). from_entry: '이 이야기 이어 하기'로 연 기록
export async function startTalk(from_entry?: string): Promise<Conversation> {
  return MOCK ? (await mock()).startTalk(from_entry) : json("POST", "/talk", from_entry ? { from_entry } : undefined);
}
export async function getTalk(id: string): Promise<Conversation> {
  return MOCK ? (await mock()).getTalk(id) : json("GET", `/talk/${encodeURIComponent(id)}`);
}
export async function deleteTalk(id: string): Promise<void> {
  if (MOCK) return (await mock()).deleteTalk(id);
  await json("DELETE", `/talk/${encodeURIComponent(id)}`);
}
// 사용자 말 한 턴 → 별지기 답이 붙은 대화. 받아쓴 말(WS21)도 같은 함수로 보낸다.
export async function sayTalk(id: string, text: string, onProgress: (p: TalkProgress) => void,
  via: "text" | "voice" = "text"): Promise<Conversation> {
  if (MOCK) return (await mock()).sayTalk(id, text, onProgress, via);
  const res = await postStream(`/talk/${encodeURIComponent(id)}/turn/stream`, { text, via }, TALK_NET);
  const reader = res.body!.getReader(), dec = new TextDecoder();
  let buf = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      const p = parseSSE(buf + dec.decode(value, { stream: true }));
      buf = p.rest;
      for (const e of p.events) {
        const d = JSON.parse(e.data);
        if (e.event === "progress") onProgress(d);
        else if (e.event === "turn") return d as Conversation;
        else if (e.event === "error") throw { ...d, entry_id: null } as StreamError;
      }
    }
  } catch (e) {
    if ((e as StreamError).code) throw e;
  }
  throw { entry_id: null, code: "disconnected", message: "연결이 끊겼어요. 대화를 다시 불러올게요.", resumable: true } as StreamError;
}
// 대화 마치고 정리하기 → 확인을 기다리는 정리(status "confirm")
export async function finishTalk(id: string, h: StreamHandlers): Promise<EntryResult> {
  if (MOCK) return (await mock()).finishTalk(id, h);
  return readStream(await postStream(`/talk/${encodeURIComponent(id)}/finish/stream`, undefined, TALK_NET), h);
}
// 요약 확인: 고친 것을 넣고 우주에 저장 → 저장된 결과(한마디 포함)
export async function confirmDiary(id: string, c: ConfirmInput): Promise<EntryResult> {
  return changed(MOCK ? await (await mock()).confirmDiary(id, c) : await json<EntryResult>("POST", `/diary/${encodeURIComponent(id)}/confirm`, c));
}

/* ---------- 사진 글자 읽기 (WS18, docs/api-v8.md) ---------- */
// 사진 한 장(화면에서 4MB 아래로 줄인 것)의 글자만 읽는다. 서버는 사진 · 읽은 글을 저장하지 않는다. 여러 쪽은 한 장씩 차례로 부른다.
let mockPage = 0;
export async function readPhoto(photo: Blob): Promise<{ text: string }> {
  if (MOCK) { await new Promise((ok) => setTimeout(ok, 300)); return { text: `(가짜 글자 읽기 ${++mockPage}번째 사진)\n오늘은 도서관에서 시험 공부를 했다.` }; }
  try {
    return (await send("/photo/read", { method: "POST", headers: { "Content-Type": photo.type || "application/octet-stream" }, body: photo })).json();
  } catch (e) {   // 배포 앞단이 막은 413 은 이유가 없다
    throw e instanceof ApiError && e.status === 413 && !e.message
      ? new ApiError(413, e.code, "사진이 너무 커요(4.5MB까지). JPG로 바꾸거나 다시 찍어 올려 주세요.") : e;
  }
}

/* ---------- 인스타그램 가져오기 (WS17, docs/api-v8.md §9) ---------- */
export type ImportPost = { ref: string; written_at: string; title: string; text: string; day: string; day_basis: "확실" | "추정";
  day_check: boolean; parts: number; too_long: boolean; imported: boolean };
export type ImportPreview = { posts: ImportPost[]; max_posts: number | null; est_seconds_per_post: number; est_usd_per_post: number };
// 게시물(캡션 · 시각) → 가져올 글 목록(최근 것부터). 저장 · 외부 전송 없음
export async function previewInstagram(posts: unknown[]): Promise<ImportPreview> {
  return json("POST", "/import/instagram/preview", { posts });
}

/* ---------- 우주 고치기 (WS16, docs/api-v8.md §4.1) ---------- */
export type SunRow = { id: string; name: string; custom: boolean; axis: string | null };
export type MergeCandidate = { a: { id: string; name: string }; b: { id: string; name: string }; sun: string | null; why: string };
const USER_AREA = "사용자 영역";
// 가짜 데이터 모드는 우주를 바꾸지 않고 모양만 돌려준다(화면 흐름 확인용)
const mockAxes = async () => [...(await import("./ontology.json")).default.domains.map((d) => d.name), USER_AREA];
export async function getSuns(): Promise<{ suns: SunRow[]; axes: string[] }> {
  if (!MOCK) return json("GET", "/suns");
  const axes = await mockAxes();
  return { suns: (await getUniverse()).suns.map((s) => ({ ...s, axis: axes.includes(s.name) ? s.name : USER_AREA })), axes };
}
export async function addSun(name: string): Promise<SunRow & { suggested: { axis: string; basis: string } }> {
  if (MOCK) return { id: "d_new", name, custom: true, axis: USER_AREA, suggested: { axis: USER_AREA, basis: "없음" } };
  return json("POST", "/suns", { name });
}
export async function setSunAxis(id: string, axis: string): Promise<SunRow> {
  return MOCK ? { id, name: id, custom: true, axis } : json("PATCH", `/suns/${encodeURIComponent(id)}`, { axis });
}
export async function moveStar(id: string, sun_id: string): Promise<{ id: string; sun_id: string; name: string }> {
  return MOCK ? { id, sun_id, name: id } : json("PATCH", `/stars/${encodeURIComponent(id)}`, { sun_id });
}
export async function getMergeCandidates(): Promise<{ candidates: MergeCandidate[] }> {
  return MOCK ? { candidates: [] } : json("GET", "/stars/merge");
}
export async function mergeStars(from_id: string, into_id: string): Promise<{ id: string; name: string }> {
  return MOCK ? { id: into_id, name: into_id } : json("POST", "/stars/merge", { from_id, into_id });
}
export async function declineMerge(from_id: string, into_id: string): Promise<{ ok: boolean }> {
  return MOCK ? { ok: true } : json("POST", "/stars/merge/decline", { from_id, into_id });
}
// 생각 종류 · 가치 고치기(value: null = 비움). 고친 값은 오답 재료로 남는다.
export async function fixThought(t: Thought, patch: { kind?: string; value?: string | null }): Promise<Thought> {
  return MOCK ? { ...t, ...patch } : json("PATCH", `/thoughts/${encodeURIComponent(t.id)}`, patch);
}
// 사람 지우기 + 그 사람이 나온 생각 · 관계도 지우기(글 본문은 이름만 관계 말로)
export async function deletePersonWithThoughts(id: string): Promise<{ ok: boolean; replaced: number; hidden: number }> {
  if (MOCK) return { ...(await deletePerson(id)), hidden: 0 };
  return json("DELETE", `/people/${encodeURIComponent(id)}/with-thoughts`);
}

/* ---------- 운영 · 선호 맞추기 제안 (WS22, docs/api-v8.md §6.2) ---------- */
export type NextDay = { pairs: number; returned: number; ratio: number | null };
export type OpsSummary = {
  generated_at: string;
  users: { total: number; active_7d: number; operator_read: number };
  cost: { total_usd: number; month_usd: number; budget_usd: number; used_ratio: number | null; warn: boolean; over: boolean;
    by_step: Record<string, number> };
  runs: { count: number; by_step: { step: string; count: number; avg_ms: number; fails: number; est_usd: number }[];
    per_entry: { entries: number; avg_s: number | null; avg_usd: number | null };
    recent: { at: string; step: string; ms: number | null; calls: number; est_usd: number; code: string | null; config: string | null; entry_id: string | null }[] };
  gates: { real_name_leak: number; voice_runs: number; voice_regenerated: number; voice_regenerated_ratio: number | null };
  failures: { entries: number; by_code: Record<string, number>; run_errors: { step: string; code: string; count: number }[];
    recent: { entry_id: string; step: string | null; code: string | null; at: string }[] };
  eval: { file: string; gate_ok: boolean | null; regressions: number; passed: number; total: number; est_usd: number | null }[] | null;
  satisfaction: { yes: number; no: number; yes_ratio: number | null; reactions: Record<string, number>;
    by_config: Record<string, Record<string, number>>; next_day: NextDay };
  direction: { multi_sun: { window_days: number; users: number; avg_suns: number | null; share_2plus: number | null; avg_suns_all: number | null };
    closer_feeling: null };
  talk: { conversations: number; avg_turns: number | null; finished: number; dropped: number; drop_at: Record<string, number>;
    stop_after_suggestion: number | null; stop_without_suggestion: number | null; confirms: number; edited_ratio: number | null;
    confirms_with_edit: number | null };
  voice: { messages: number; suggested_ratio: number | null; repeat_ratio: number | null; dislike_ratio: number | null;
    next_day_with_suggestion: NextDay; next_day_without_suggestion: NextDay };
  other_values: { thoughts: number; kind: number; certainty: number; value: number };
  feedback_text: { consented: number; not_consented: number };
};
export type OpsFeedback = { days: number; wrong: boolean; users: number;
  items: { user: string; at: string; target: string; value: string; text: string | null; target_text: string | null; config: string | null }[];
  other_candidates: { field: string; original: string; count: number }[]; not_consented: Record<string, number> };
export type OpsDigest = { days: number; users: number; lines: string[]; est_usd: number;
  groups: { reason: string; items: number[]; count: number; fix_where: string; suggestion: string }[] };
export type PrefSuggestion = { setting: "cross_links" | "suggestions"; from: string; to: string; reason: string };
const mockOps = () => import("./mock-ops");
export async function getOpsSummary(): Promise<OpsSummary> {
  return MOCK ? (await mockOps()).summary : json("GET", "/ops/summary");
}
// 동의한 사용자의 피드백 원문(가명). 부를 때마다 서버에 열람 기록이 남는다
export async function getOpsFeedback(days = 30): Promise<OpsFeedback> {
  return MOCK ? (await mockOps()).feedback : json("GET", `/ops/feedback?days=${days}`);
}
export async function summarizeFeedback(days = 30): Promise<OpsDigest> {
  return MOCK ? (await mockOps()).digest : json("POST", `/ops/feedback/summarize?days=${days}`);
}
export async function getPrefSuggestions(): Promise<{ suggestions: PrefSuggestion[] }> {
  return MOCK ? { suggestions: [] } : json("GET", "/settings/suggestions");
}
export async function markPrefSeen(): Promise<{ ok: boolean }> {
  return MOCK ? { ok: true } : json("POST", "/settings/suggestions/seen");
}

/* ---------- 말로 쓰기 · 읽어 주기 (WS21, docs/api-v8.md §10) ---------- */
// 녹음 조각 하나(4MB 아래) → 받아쓴 글. 긴 녹음 나누기 · 이어 붙이기는 components/MicButton.tsx
export async function transcribe(piece: Blob): Promise<{ text: string; seconds: number }> {
  if (MOCK) return (await mock()).transcribe(piece);
  return (await send("/voice/transcribe", { method: "POST", body: piece, headers: { "Content-Type": piece.type || "application/octet-stream" } })).json();
}
// 별지기 말 → mp3
export async function speak(text: string): Promise<Blob> {
  return MOCK ? (await mock()).speak(text) : (await req("POST", "/voice/speak", { text })).blob();
}
