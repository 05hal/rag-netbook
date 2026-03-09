import os
import sys

# 强制 Python 进程使用 UTF-8 编码
os.environ["PYTHONIOENCODING"] = "utf-8"

# 再次确认标准输出流
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# 允许跨域，否则 HBuilderX 或小程序模拟器会报错
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(data: dict = Body(...)):
    # 获取前端传来的参数
    content = data.get("content")
    chapter_id = data.get("chapter_id")
    
    print(f"收到请求: 章节={chapter_id}, 内容={content}")

    # --- 这里预留给队友的 RAG 函数 ---
    # reply = your_teammate_rag_function(content, chapter_id)
    # ------------------------------
    
    # 目前先返回模拟数据
    prefix = f"【来自第{chapter_id}章的检索】" if chapter_id else "【全局检索】"
    return {
        "reply": f"{prefix} 你好，我是你的计网助教。关于'{content}'，根据教材规定..."
    }

if __name__ == "__main__":
    # 使用 0.0.0.0 允许局域网内的手机访问
    uvicorn.run(app, host="0.0.0.0", port=8000)