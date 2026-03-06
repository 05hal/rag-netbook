import os
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS


# =========================
# 1. 环境变量
# =========================
load_dotenv()

VECTOR_DB_ROOT = os.getenv("VECTOR_DB_ROOT", "vector_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

# 你的模型 API 配置（按 OpenAI 兼容接口写）
LLM_API_BASE = os.getenv("LLM_API_BASE", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")

# 小程序跨域时常用；开发阶段可以先全开放
ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"


# =========================
# 2. Embedding 封装
# =========================
class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        emb = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return emb.astype(np.float32).tolist()

    def embed_query(self, text: str) -> List[float]:
        emb = self.model.encode(
            [text],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]
        return emb.astype(np.float32).tolist()


# =========================
# 3. FastAPI 初始化
# =========================
app = FastAPI(title="RAG Backend", version="1.0.0")

if ENABLE_CORS:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境建议改成你的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# =========================
# 4. 全局变量
# =========================
embedding_model: Optional[SentenceTransformerEmbeddings] = None
VECTOR_DBS: Dict[str, FAISS] = {}


# =========================
# 5. 请求/响应模型
# =========================
ChapterType = Literal["all", "1", "2", "3", "4", "5", "6", "7", "8"]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    chapter: ChapterType = Field(default="all", description="指定章节或 all")
    top_k: int = Field(default=4, ge=1, le=10, description="返回候选数量")


class SourceItem(BaseModel):
    chapter: str
    path: str
    chunk_id: str
    content: str


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


# =========================
# 6. 工具函数
# =========================
def should_skip_doc(path: str) -> bool:
    bad_words = ["附录", "参考文献", "习题答案", "索引"]
    return any(x in path for x in bad_words)


def chapter_db_path(chapter: int) -> str:
    return os.path.join(VECTOR_DB_ROOT, f"ch{chapter}_faiss")


def load_all_vector_dbs() -> None:
    global embedding_model, VECTOR_DBS

    embedding_model = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
    VECTOR_DBS.clear()

    for i in range(1, 9):
        path = chapter_db_path(i)
        if os.path.exists(path):
            VECTOR_DBS[str(i)] = FAISS.load_local(
                path,
                embedding_model,
                allow_dangerous_deserialization=True,
            )

    if not VECTOR_DBS:
        raise RuntimeError(f"未找到任何向量库，请检查目录：{VECTOR_DB_ROOT}")


def search_one_chapter(question: str, chapter: str, top_k: int) -> List:
    db = VECTOR_DBS.get(chapter)
    if not db:
        return []

    # 用 with_score，方便全书排序统一
    hits = db.similarity_search_with_score(question, k=top_k)
    docs = []
    for doc, score in hits:
        doc.metadata["chapter"] = chapter
        doc.metadata["_score"] = float(score)
        docs.append(doc)
    return docs


def search_all_chapters(question: str, top_k_each: int = 2, final_k: int = 5) -> List:
    all_docs = []

    for chapter, db in VECTOR_DBS.items():
        hits = db.similarity_search_with_score(question, k=top_k_each)
        for doc, score in hits:
            doc.metadata["chapter"] = chapter
            doc.metadata["_score"] = float(score)
            all_docs.append(doc)

    # FAISS 距离一般越小越相近
    all_docs.sort(key=lambda d: d.metadata.get("_score", 1e9))
    return all_docs[:final_k]


def retrieve_docs(question: str, chapter: str, top_k: int) -> List:
    if chapter == "all":
        docs = search_all_chapters(question, top_k_each=2, final_k=top_k)
    else:
        docs = search_one_chapter(question, chapter, top_k)

    filtered = []
    seen = set()

    for doc in docs:
        path = str(doc.metadata.get("path", ""))
        chunk_id = str(doc.metadata.get("chunk_id", ""))
        key = (path, chunk_id)

        if should_skip_doc(path):
            continue
        if key in seen:
            continue

        seen.add(key)
        filtered.append(doc)

    return filtered


def build_prompt(question: str, docs: List) -> str:
    if not docs:
        context = "没有检索到可用教材资料。"
    else:
        blocks = []
        for i, doc in enumerate(docs, start=1):
            chapter = str(doc.metadata.get("chapter", ""))
            path = str(doc.metadata.get("path", ""))
            chunk_id = str(doc.metadata.get("chunk_id", ""))
            content = doc.page_content.strip()

            block = (
                f"[资料{i}]\n"
                f"章节: 第{chapter}章\n"
                f"路径: {path}\n"
                f"块ID: {chunk_id}\n"
                f"内容: {content}"
            )
            blocks.append(block)

        context = "\n\n".join(blocks)

    prompt = f"""
你是一个计算机网络教材问答助手。
请严格依据给定教材资料回答，不要编造。
如果资料不足以回答，请明确说：“根据当前教材内容无法确定”。

【用户问题】
{question}

【教材资料】
{context}

请按以下格式输出：
1. 直接答案
2. 依据说明
3. 引用资料编号
""".strip()

    return prompt


def call_llm_api(prompt: str) -> str:
    """
    这里按 OpenAI 兼容接口写：
    POST {LLM_API_BASE}/chat/completions

    你只需要把 .env 配成自己的模型 API 即可。
    """
    if not LLM_API_BASE or not LLM_API_KEY or not LLM_MODEL_NAME:
        raise RuntimeError("LLM_API_BASE / LLM_API_KEY / LLM_MODEL_NAME 未正确配置")

    url = f"{LLM_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是一个严格依据教材资料回答问题的助手。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"模型 API 调用失败: {resp.status_code} {resp.text}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError(f"模型 API 返回格式异常: {data}") from e


# =========================
# 7. 生命周期
# =========================
@app.on_event("startup")
def startup_event():
    load_all_vector_dbs()
    print("向量库加载完成：", list(VECTOR_DBS.keys()))


# =========================
# 8. 路由
# =========================
@app.get("/health")
def health():
    return {
        "ok": True,
        "loaded_chapters": list(VECTOR_DBS.keys()),
        "embedding_model": EMBEDDING_MODEL,
        "vector_db_root": VECTOR_DB_ROOT,
    }


@app.post("/api/rag/ask", response_model=AskResponse)
def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    if req.chapter != "all" and req.chapter not in VECTOR_DBS:
        raise HTTPException(status_code=400, detail=f"第 {req.chapter} 章向量库未加载")

    docs = retrieve_docs(question, req.chapter, req.top_k)
    prompt = build_prompt(question, docs)

    try:
        answer = call_llm_api(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sources = []
    for doc in docs:
        sources.append(
            SourceItem(
                chapter=str(doc.metadata.get("chapter", "")),
                path=str(doc.metadata.get("path", "")),
                chunk_id=str(doc.metadata.get("chunk_id", "")),
                content=doc.page_content[:300],
            )
        )

    return AskResponse(answer=answer, sources=sources)