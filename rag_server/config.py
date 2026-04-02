import os
from dotenv import load_dotenv

# =========================
# 环境变量
# =========================
load_dotenv()

VECTOR_DB_ROOT = os.getenv("VECTOR_DB_ROOT", "vector_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

# OpenAI 兼容接口配置
LLM_API_BASE = os.getenv("LLM_API_BASE", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "")

# 小程序跨域时常用；开发阶段可以先全开放
ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"