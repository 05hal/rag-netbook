from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import ENABLE_CORS
from routes import router
from services import VECTOR_DBS, load_all_vector_dbs


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_all_vector_dbs()
    print("向量库加载完成：", list(VECTOR_DBS.keys()))
    yield
    # 这里可放关闭资源的逻辑


app = FastAPI(
    title="RAG Backend",
    version="1.0.0",
    lifespan=lifespan,
)

if ENABLE_CORS:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境建议改成具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(router)