// 온톨로지 단일 기준(app/core/ontology/v8.json)을 화면 쪽으로 복사한다. 손으로 다시 적지 않는다.
// 가짜 데이터 모드의 GET /ontology 응답과 타입 검사에 쓴다. v8.json 이 바뀌면 `npm run sync:ontology`.
import { copyFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const src = fileURLToPath(new URL("../../../app/core/ontology/v8.json", import.meta.url));
const dst = fileURLToPath(new URL("../lib/ontology.json", import.meta.url));
mkdirSync(fileURLToPath(new URL("../lib/", import.meta.url)), { recursive: true });
copyFileSync(src, dst);
console.log("복사함:", src, "->", dst);
