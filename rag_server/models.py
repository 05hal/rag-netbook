from typing import List, Literal

import numpy as np
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from langchain_core.embeddings import Embeddings


# =========================
# Embedding 封装
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
# 请求/响应模型
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


from typing import Optional


DifficultyType = Literal["easy", "medium", "hard"]
QuestionType = Literal["single", "judge", "short_answer"]


class GenerateExercisesRequest(BaseModel):
    chapter: ChapterType = Field(..., description="指定章节")
    difficulty: DifficultyType = Field(..., description="题目难度：easy / medium / hard")
    count: int = Field(default=5, ge=1, le=10, description="生成题目数量")
    top_k: int = Field(default=6, ge=1, le=12, description="检索教材片段数量")
    with_answer: bool = Field(default=True, description="是否返回参考答案")


class ExerciseItem(BaseModel):
    question_type: QuestionType
    difficulty: DifficultyType
    stem: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)


class GenerateExercisesResponse(BaseModel):
    chapter: str
    difficulty: DifficultyType
    exercises: List[ExerciseItem]
    sources: List[SourceItem]