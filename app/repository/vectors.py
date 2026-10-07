"""
app/repository/vectors.py

생각 벡터 저장소(ChromaDB 하나). 컬렉션 thoughts: id = 생각 id, 메타 = user_id · entry_id · star_id · written_at · kind.
문서(원문)는 넣지 않는다. 벡터는 가명 처리한 글로 만든 임베딩이다. 모든 읽기 · 지우기는 user_id 로 거른다.
"""

from app.core import config


class ChromaVectors:
    def __init__(self):
        import chromadb
        if config.CHROMA_API_KEY:   # 배포: Chroma Cloud
            c = chromadb.CloudClient(tenant=config.CHROMA_TENANT or None, database=config.CHROMA_DATABASE or None,
                                     api_key=config.CHROMA_API_KEY)
        else:
            c = chromadb.HttpClient(host=config.CHROMA_HOST, port=config.CHROMA_PORT)
        self.col = c.get_or_create_collection(config.CHROMA_COLLECTION, embedding_function=None,
                                              metadata={"hnsw:space": "cosine"})

    def upsert(self, uid, items):
        """items: [{id, emb, entry_id, star_id, written_at, kind}]"""
        if items:
            self.col.upsert(ids=[i["id"] for i in items], embeddings=[i["emb"] for i in items],
                            metadatas=[{"user_id": str(uid), **{k: str(i.get(k) or "") for k in
                                                                ("entry_id", "star_id", "written_at", "kind")}}
                                       for i in items])

    def get(self, uid, ids=None):
        """{생각 id: 벡터}. ids 가 없으면 그 사용자 것 전부."""
        # ponytail: 사용자 벡터를 전부 읽는다(글 수백 편이면 충분). 수천 편이 넘으면 query(n_results) 로 바꾼다.
        r = self.col.get(ids=list(ids) if ids else None, where={"user_id": str(uid)}, include=["embeddings"])
        return {i: list(map(float, e)) for i, e in zip(r["ids"], r["embeddings"])}

    def delete(self, uid, ids=None, entry_id=None):
        where = {"user_id": str(uid)} if not entry_id else {"$and": [{"user_id": str(uid)}, {"entry_id": entry_id}]}
        if ids is not None and not ids:
            return
        self.col.delete(ids=list(ids) if ids else None, where=where)

    def documents(self, uid):
        """시험용: 저장된 문서 · 메타(원문이 없는지 확인)."""
        r = self.col.get(where={"user_id": str(uid)}, include=["documents", "metadatas"])
        return r["documents"], r["metadatas"]


class MemVectors:
    def __init__(self):
        self.items = {}

    def upsert(self, uid, items):
        for i in items:
            self.items[i["id"]] = {"user_id": str(uid), **i}

    def get(self, uid, ids=None):
        return {k: v["emb"] for k, v in self.items.items() if v["user_id"] == str(uid) and (ids is None or k in ids)}

    def delete(self, uid, ids=None, entry_id=None):
        for k in [k for k, v in self.items.items() if v["user_id"] == str(uid)
                  and (ids is None or k in ids) and (entry_id is None or v["entry_id"] == entry_id)]:
            del self.items[k]

    def documents(self, uid):
        return [None for v in self.items.values() if v["user_id"] == str(uid)], \
            [{k: v[k] for k in ("entry_id", "star_id", "written_at", "kind")} for v in self.items.values() if v["user_id"] == str(uid)]
