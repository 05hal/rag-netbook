import os
import json
import time
import argparse
from typing import List, Dict, Any

import numpy as np
from tqdm import tqdm

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddings(Embeddings):
    """
    让 sentence-transformers 以 LangChain Embeddings 接口工作，
    方便 FAISS.from_documents() 直接使用。
    """
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", batch_size: int = 64):
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)

        # 可选：如果你机器有GPU且已装好CUDA+torch，可自动用cuda
        # self.model = SentenceTransformer(model_name, device="cuda")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            emb = self.model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,  # 建议归一化，余弦效果更稳
            )
            vectors.extend(emb.astype(np.float32).tolist())
        return vectors

    def embed_query(self, text: str) -> List[float]:
        emb = self.model.encode(
            [text],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]
        return emb.astype(np.float32).tolist()


def load_jsonl_documents(jsonl_path: str) -> List[Document]:
    docs: List[Document] = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            text = obj.get("text", "")
            meta = obj.get("meta", {})
            if not isinstance(meta, dict):
                meta = {}
            if not text:
                continue
            docs.append(Document(page_content=text, metadata=meta))
    return docs


def main():
    parser = argparse.ArgumentParser(description="Build FAISS vector DB from chunks jsonl")
    parser.add_argument("--chunks", default="chunks/chapter1_chunks.jsonl", help="输入chunks jsonl路径")
    parser.add_argument("--out", default="vector_db/ch1_faiss", help="输出FAISS目录（会生成index.faiss/index.pkl）")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5", help="SentenceTransformer模型名")
    parser.add_argument("--batch_size", type=int, default=64, help="embedding batch size")
    parser.add_argument("--k_test", type=int, default=3, help="建库后做一次简单检索测试返回k条")
    args = parser.parse_args()

    chunks_path = args.chunks
    out_dir = args.out
    model_name = args.model

    if not os.path.exists(chunks_path):
        raise FileNotFoundError(f"找不到 chunks 文件：{chunks_path}")

    os.makedirs(out_dir, exist_ok=True)

    print(f"[1/4] Load chunks: {chunks_path}")
    docs = load_jsonl_documents(chunks_path)
    if not docs:
        raise RuntimeError("没有加载到任何chunk，请检查jsonl格式和路径。")

    lengths = [len(d.page_content) for d in docs]
    print(f"  docs={len(docs)} len(min/avg/max)={min(lengths)}/{sum(lengths)//len(lengths)}/{max(lengths)}")

    print(f"[2/4] Init embedding model: {model_name}")
    emb = SentenceTransformerEmbeddings(model_name=model_name, batch_size=args.batch_size)

    print("[3/4] Build FAISS index ...")
    t0 = time.time()
    db = FAISS.from_documents(docs, emb)
    dt = time.time() - t0
    print(f"  FAISS built in {dt:.2f}s")

    print(f"[4/4] Save FAISS to: {out_dir}")
    db.save_local(out_dir)
    print("  Saved: index.faiss + index.pkl")

    # ------- 简单自检：检索一下 -------
    query = "谁是钱天白教授，做了什么杰出贡献"
    print("\n[Self-test] query:", query)
    hits = db.similarity_search(query, k=args.k_test)
    for i, h in enumerate(hits, start=1):
        path = h.metadata.get("path", "")
        cid = h.metadata.get("chunk_id", "")
        print(f"\n--- hit {i} --- path={path} chunk_id={cid} len={len(h.page_content)}")
        print(h.page_content[:200])


if __name__ == "__main__":
    main()