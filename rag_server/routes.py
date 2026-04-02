from fastapi import APIRouter

from config import EMBEDDING_MODEL, VECTOR_DB_ROOT
from models import AskRequest, AskResponse
from services import VECTOR_DBS, ask_question

from models import AskRequest, AskResponse, GenerateExercisesRequest, GenerateExercisesResponse
from services import VECTOR_DBS, ask_question, generate_exercises

router = APIRouter()


@router.get("/health")
def health():
    return {
        "ok": True,
        "loaded_chapters": list(VECTOR_DBS.keys()),
        "embedding_model": EMBEDDING_MODEL,
        "vector_db_root": VECTOR_DB_ROOT,
    }


@router.post("/api/rag/ask", response_model=AskResponse)
def ask(req: AskRequest):
    return ask_question(req)

@router.post("/api/rag/generate-exercises", response_model=GenerateExercisesResponse)
def generate_exercises_api(req: GenerateExercisesRequest):
    return generate_exercises(req)