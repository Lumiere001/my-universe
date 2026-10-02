"""
agent_client.py

Studio Agent 실행 모듈 (기록 Agent · 관측 Agent 공통)

- Files API로 HTML을 올리고 Jobs API로 실행한다 (include=all: Parse · Classify · Extract 결과).
- 같은 입력 · 같은 설정은 캐시에서 돌려준다 (로컬 개발 전용, config.DISK_CACHE).
  화면에서는 우주에 이미 있는 글을 건너뛰는 것으로 "이미 정리된 글은 다시 보내지 않는다"를 지킨다.
- 실패하면 한 번 다시 시도한다.
"""

import hashlib
import json
import time

from openai import OpenAI

import config

client = OpenAI(api_key=config.UPSTAGE_API_KEY, base_url="https://api.upstage.ai/v2")
CACHE_DIR = config.RUNS_DIR / "cache"


class AgentError(RuntimeError):
    pass


class AgentClient:

    def __init__(self, agent_id, config_id="1", name="agent"):
        self.agent_id = agent_id
        self.config_id = str(config_id)
        self.name = name

    def run_html(self, html: str, use_cache=True, timeout=180):
        """HTML 문서 한 개를 실행해 (분류 결과, 추출 JSON, 실행 정보)를 돌려준다."""
        key = hashlib.sha256(f"{self.agent_id}:{self.config_id}:{html}".encode()).hexdigest()[:24]
        cached = CACHE_DIR / f"{key}.json"
        if use_cache and config.DISK_CACHE and cached.exists():
            hit = json.loads(cached.read_text(encoding="utf-8"))
            return hit["label"], hit["data"], dict(hit["meta"], cached=True)   # 원래 실행의 시간·비용을 그대로 보여 준다

        last = None
        for attempt in (1, 2):
            try:
                label, data, meta = self._run_once(html, timeout)
                meta["attempts"] = attempt
                if config.DISK_CACHE:
                    CACHE_DIR.mkdir(parents=True, exist_ok=True)
                    cached.write_text(json.dumps({"label": label, "data": data, "meta": meta}, ensure_ascii=False), encoding="utf-8")
                return label, data, dict(meta, cached=False)
            except Exception as e:  # 네트워크 · 실패 상태 · JSON 아님
                last = e
                time.sleep(2)
        raise AgentError(f"{self.name} 실행 실패: {last}")

    def _run_once(self, html, timeout):
        t0 = time.time()
        uploaded = client.files.create(file=("input.html", html.encode("utf-8"), "text/html"), purpose="user_data")
        r = client.responses.create(
            model=self.agent_id,
            include=["all"],
            input=[{"role": "user", "content": [{"type": "input_file", "file_id": uploaded.id}]}],
            extra_body={"config_id": self.config_id},
        )
        while r.status in ("queued", "in_progress"):
            if time.time() - t0 > timeout:
                raise AgentError("시간 초과")
            time.sleep(1.5)
            r = client.responses.retrieve(r.id, include=["all"])
        if r.status != "completed":
            raise AgentError(f"상태: {r.status}")

        steps = [o.content[0].text for o in r.output if getattr(o, "content", None)]
        if len(steps) < 3:
            raise AgentError(f"단계 결과가 {len(steps)}개뿐")
        parse, label = json.loads(steps[0]), steps[1].strip()
        try:
            data = json.loads(steps[-1])
        except json.JSONDecodeError:
            raise AgentError("추출 결과가 JSON 형식이 아님")
        pages = max([e.get("page", 1) for e in parse.get("elements", [])] or [1])
        meta = {
            "agent": self.name, "config_id": self.config_id, "job_id": r.id,
            "seconds": round(time.time() - t0, 2), "pages": pages,
            "est_cost": round(pages * (config.PRICE_PARSE + config.PRICE_EXTRACT), 4),
            "studio_cached": (getattr(r, "metadata", None) or {}).get("cached") == "true",
        }
        return label, data, meta


record_agent = AgentClient(config.RECORD_AGENT_ID, config.RECORD_CONFIG_ID, "기록 Agent")
observe_agent = AgentClient(config.OBSERVE_AGENT_ID, config.OBSERVE_CONFIG_ID, "관측 Agent")
