"""규칙 v8(WS3). 순수 함수만: 입력 dict · list → 출력 dict. DB · 네트워크에 묶이지 않는다."""
from app.service.rules.gate import clean_text, strip_ids
from app.service.rules.normalize import clean_record, normalize, other_candidates, people_of
from app.service.rules.past import pick_past
from app.service.rules.relations import filter_relations
from app.service.rules.states import advance, due_vows, parse_due, press, reask_trigger
from app.service.rules.topics import cos, link_domain, match_topic, merge_candidates, sun_list, topic_input
from app.service.rules.view import universe_view

__all__ = ["normalize", "other_candidates", "people_of", "clean_record", "topic_input", "match_topic",
           "merge_candidates", "link_domain", "sun_list", "cos", "pick_past", "filter_relations", "advance",
           "press", "due_vows", "parse_due", "universe_view", "clean_text", "strip_ids", "reask_trigger"]
