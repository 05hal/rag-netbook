import os
from typing import Dict, List, Optional
import json
import re

import requests
from fastapi import HTTPException
from langchain_community.vectorstores import FAISS

from config import (
    VECTOR_DB_ROOT,
    EMBEDDING_MODEL,
    LLM_API_BASE,
    LLM_API_KEY,
    LLM_MODEL_NAME,
)
from models import (
    AskRequest,
    AskResponse,
    SentenceTransformerEmbeddings,
    GenerateExercisesRequest,
    GenerateExercisesResponse,
    ExerciseItem,
)
from utils import should_skip_doc, build_sources


# =========================
# 全局状态
# =========================
embedding_model: Optional[SentenceTransformerEmbeddings] = None
VECTOR_DBS: Dict[str, FAISS] = {}


# =========================
# 向量库相关
# =========================
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


# =========================
# Prompt 构造
# =========================
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


# =========================
# LLM 调用
# =========================
def call_llm_api(prompt: str) -> str:
    """
    这里按 OpenAI 兼容接口写：
    POST {LLM_API_BASE}/chat/completions
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
# 业务逻辑
# =========================
def ask_question(req: AskRequest) -> AskResponse:
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

    return AskResponse(
        answer=answer,
        sources=build_sources(docs),
    )

def build_exercise_prompt(
    chapter: str,
    difficulty: str,
    count: int,
    docs: List,
    with_answer: bool = True,
) -> str:
    if not docs:
        context = "没有检索到可用教材资料。"
    else:
        blocks = []
        for i, doc in enumerate(docs, start=1):
            chapter_no = str(doc.metadata.get("chapter", ""))
            path = str(doc.metadata.get("path", ""))
            chunk_id = str(doc.metadata.get("chunk_id", ""))
            content = doc.page_content.strip()

            block = (
                f"[资料{i}]\n"
                f"章节: 第{chapter_no}章\n"
                f"路径: {path}\n"
                f"块ID: {chunk_id}\n"
                f"内容: {content}"
            )
            blocks.append(block)

        context = "\n\n".join(blocks)

    difficulty_desc = {
        "easy": "简单题：侧重基础概念、定义、直接记忆与识别，不要跨越太多知识点。",
        "medium": "中等题：侧重概念理解、比较分析、简单推理，可结合小场景。",
        "hard": "困难题：侧重综合分析、机制理解、应用场景和易错点辨析，但必须严格依据教材内容。"
    }[difficulty]

    answer_rule = (
        "每道题必须包含 answer 和 explanation 字段。"
        if with_answer
        else "不要返回 answer 和 explanation 字段，可置为 null。"
    )

    prompt = f"""
你是一个计算机网络教材出题助手。
请严格依据给定教材资料出题，不要编造教材之外的知识点。
如果资料不足以支撑出题，请返回空数组。

【出题目标】
基于第{chapter}章内容，生成 {count} 道 {difficulty} 难度的习题。

【难度要求】
{difficulty_desc}

【题型范围】
可从以下三种题型中选择：
- single：单选题
- judge：判断题
- short_answer：简答题

【出题要求】
1. 题目必须紧扣教材内容。
2. single 题必须提供 4 个选项。
3. judge 题答案只能是“对”或“错”。
4. short_answer 题答案要简洁。
5. 每道题都要给出 source_refs，例如 ["资料1"] 或 ["资料1", "资料2"]。
6. {answer_rule}

【教材资料】
{context}

【输出要求】
只返回合法 JSON，不要输出解释文字，不要加 markdown。

JSON 格式如下：
{{
  "exercises": [
    {{
      "question_type": "single",
      "difficulty": "{difficulty}",
      "stem": "题干",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "explanation": "解析",
      "source_refs": ["资料1"]
    }}
  ]
}}
""".strip()

    return prompt


def parse_exercise_json(text: str) -> List[dict]:
    text = text.strip()

    try:
        data = json.loads(text)
        exercises = data.get("exercises", [])
        if isinstance(exercises, list):
            return exercises
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise RuntimeError("模型未返回合法 JSON")

    try:
        data = json.loads(match.group(0))
        exercises = data.get("exercises", [])
        if not isinstance(exercises, list):
            raise RuntimeError("exercises 字段不是数组")
        return exercises
    except Exception as e:
        raise RuntimeError(f"题目 JSON 解析失败: {text}") from e


def generate_exercises(req: GenerateExercisesRequest) -> GenerateExercisesResponse:
    if req.chapter == "all":
        raise HTTPException(status_code=400, detail="自动出题必须指定具体章节，不能使用 all")

    if req.chapter not in VECTOR_DBS:
        raise HTTPException(status_code=400, detail=f"第 {req.chapter} 章向量库未加载")

    docs = retrieve_docs(
        question=f"第{req.chapter}章 核心概念 定义 原理 重点知识",
        chapter=req.chapter,
        top_k=req.top_k,
    )

    if not docs:
        return GenerateExercisesResponse(
            chapter=req.chapter,
            difficulty=req.difficulty,
            exercises=[],
            sources=[],
        )

    prompt = build_exercise_prompt(
        chapter=req.chapter,
        difficulty=req.difficulty,
        count=req.count,
        docs=docs,
        with_answer=req.with_answer,
    )

    try:
        raw = call_llm_api(prompt)
        exercise_dicts = parse_exercise_json(raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    exercises = []
    for item in exercise_dicts:
        stem = str(item.get("stem", "")).strip()
        if not stem:
            continue

        exercises.append(
            ExerciseItem(
                question_type=item.get("question_type", "short_answer"),
                difficulty=req.difficulty,
                stem=stem,
                options=item.get("options"),
                answer=item.get("answer"),
                explanation=item.get("explanation"),
                source_refs=item.get("source_refs", []),
            )
        )

    return GenerateExercisesResponse(
        chapter=req.chapter,
        difficulty=req.difficulty,
        exercises=exercises,
        sources=build_sources(docs),
    )