# rag_server

基于 FastAPI 的教材 RAG 后端服务，实现：

- 按章节检索教材向量库
- 调用大模型生成回答
- 返回答案及对应教材来源片段

---

## 项目结构

```text
rag_server/
├─ main.py      # 应用入口，加载向量库并启动服务
├─ config.py    # 环境变量配置
├─ models.py    # 数据模型与 Embedding 封装
├─ services.py  # 向量检索、Prompt 构造、LLM 调用核心逻辑
├─ routes.py    # 接口定义
└─ utils.py     # 工具函数
环境配置

安装依赖：

pip install fastapi uvicorn python-dotenv requests sentence-transformers langchain-community langchain-core faiss-cpu

配置 .env：

VECTOR_DB_ROOT=vector_db
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
LLM_API_BASE=your_api_base
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=your_model

*******************************************************************************************************************************
启动方式
uvicorn main:app --reload

*******************************************************************************************************************************

访问：

http://127.0.0.1:8000/health
接口示例

POST：

/api/rag/ask

请求：

{
  "question": "什么是分组交换？",
  "chapter": "2"
}

返回：

{
  "answer": "...",
  "sources": [...]
}

如果这是课程项目 README，这个长度基本是**老师最喜欢的标准版**：结构清晰、能跑、能测、不过度解释。