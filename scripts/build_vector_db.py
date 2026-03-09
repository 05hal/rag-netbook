import os
import re
import json
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from collections import Counter

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

        # 如果你之后确认 CUDA 环境没问题，可改成：
        # self.model = SentenceTransformer(model_name, device="cuda")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            emb = self.model.encode(
                batch,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
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


def discover_chunk_files(chunks_dir: str) -> List[str]:
    files = []
    for name in os.listdir(chunks_dir):
        if name.endswith("_chunks.jsonl"):
            files.append(os.path.join(chunks_dir, name))
    files.sort()
    return files


def infer_output_dir(jsonl_path: str, out_root: str) -> str:
    """
    chapter1_chunks.jsonl -> vector_db/ch1_faiss
    chapter12_chunks.jsonl -> vector_db/ch12_faiss
    """
    base = os.path.basename(jsonl_path)
    m = re.match(r"chapter(\d+)_chunks\.jsonl$", base, re.IGNORECASE)
    if m:
        ch_num = m.group(1)
        return os.path.join(out_root, f"ch{ch_num}_faiss")

    # 兜底
    stem = os.path.splitext(base)[0]
    stem = stem.replace("_chunks", "")
    return os.path.join(out_root, f"{stem}_faiss")


def extract_candidate_titles(docs: List[Document]) -> List[str]:
    titles = []
    for d in docs:
        meta = d.metadata or {}
        for key in ["h1", "h2", "h3", "h4", "path"]:
            val = meta.get(key, "")
            if isinstance(val, str) and val.strip():
                titles.append(val.strip())
    return titles


def extract_keywords_from_docs(docs: List[Document], topn: int = 10) -> List[str]:
    """
    很轻量的关键词抽取，不依赖jieba。
    规则：
    - 提取连续中文词串 / 英文术语 / 数字字母组合
    - 去掉很短或太常见的词
    """
    stopwords = {
        "本章", "本节", "这一章", "一种", "进行", "通过", "以及", "有关", "内容",
        "概念", "方法", "作用", "结构", "工作", "过程", "系统", "网络", "计算机",
        "可以", "包括", "使用", "一个", "多个", "就是", "什么", "中的", "主要",
        "如果", "由于", "为了", "然后", "其中", "我们", "你们", "他们"
    }

    counter = Counter()
    for d in docs[:8]:  # 前几块通常更能代表章节主题
        text = d.page_content
        tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9\-\._]{1,20}", text)
        for tok in tokens:
            tok = tok.strip()
            if len(tok) < 2:
                continue
            if tok in stopwords:
                continue
            counter[tok] += 1

    keywords = [w for w, _ in counter.most_common(topn)]
    return keywords


def generate_test_query(docs: List[Document]) -> str:
    """
    根据章节内容自动生成一个适合做自检的 query。
    优先级：
    1. h2/h3标题
    2. path
    3. 高频关键词
    4. 兜底：本章主要讲了什么
    """
    titles = extract_candidate_titles(docs)

    # 优先选较具体的标题
    preferred = []
    for t in titles:
        if ">" in t:
            continue
        if 2 <= len(t) <= 30:
            preferred.append(t)

    for t in preferred:
        if any(x in t for x in ["概述", "简介", "引言"]):
            continue
        return f"请解释 {t} 的含义和作用"

    keywords = extract_keywords_from_docs(docs, topn=10)
    if len(keywords) >= 2:
        return f"{keywords[0]} 和 {keywords[1]} 有什么关系"
    elif len(keywords) == 1:
        return f"什么是 {keywords[0]}"

    return "本章主要讲了什么"


def build_one_db(jsonl_path: str, out_dir: str, emb: SentenceTransformerEmbeddings, k_test: int = 3):
    print(f"\n{'=' * 70}")
    print(f"[Build] chunks: {jsonl_path}")

    docs = load_jsonl_documents(jsonl_path)
    if not docs:
        print("  [Skip] 没有加载到任何 chunk")
        return

    lengths = [len(d.page_content) for d in docs]
    print(f"  docs={len(docs)} len(min/avg/max)={min(lengths)}/{sum(lengths)//len(lengths)}/{max(lengths)}")

    os.makedirs(out_dir, exist_ok=True)

    print(f"  [1] Build FAISS -> {out_dir}")
    t0 = time.time()
    db = FAISS.from_documents(docs, emb)
    dt = time.time() - t0
    print(f"      built in {dt:.2f}s")

    print("  [2] Save FAISS")
    db.save_local(out_dir)
    print("      saved: index.faiss + index.pkl")

    query = generate_test_query(docs)
    print(f"  [3] Self-test query: {query}")

    hits = db.similarity_search(query, k=k_test)
    for i, h in enumerate(hits, start=1):
        path = h.metadata.get("path", "")
        cid = h.metadata.get("chunk_id", "")
        print(f"      --- hit {i} --- path={path} chunk_id={cid} len={len(h.page_content)}")
        print(f"      {h.page_content[:120].replace(chr(10), ' ')}")


def main():
    parser = argparse.ArgumentParser(description="Build FAISS vector DB from one or all chunks jsonl")
    parser.add_argument("--chunks", default=None, help="单个 chunks jsonl 路径，例如 chunks/chapter1_chunks.jsonl")
    parser.add_argument("--chunks_dir", default=None, help="批量扫描 chunks 目录，例如 chunks")
    parser.add_argument("--out", default=None, help="单文件模式输出目录，例如 vector_db/ch1_faiss")
    parser.add_argument("--out_dir", default="vector_db", help="批量模式输出根目录，例如 vector_db")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5", help="SentenceTransformer 模型名")
    parser.add_argument("--batch_size", type=int, default=64, help="embedding batch size")
    parser.add_argument("--k_test", type=int, default=3, help="建库后自检返回 k 条")
    args = parser.parse_args()

    if not args.chunks and not args.chunks_dir:
        raise ValueError("请至少提供 --chunks 或 --chunks_dir 其中一个参数")

    print(f"[Init] embedding model: {args.model}")
    emb = SentenceTransformerEmbeddings(model_name=args.model, batch_size=args.batch_size)

    # ---------- 单文件模式 ----------
    if args.chunks:
        if not os.path.exists(args.chunks):
            raise FileNotFoundError(f"找不到 chunks 文件：{args.chunks}")

        out_dir = args.out
        if not out_dir:
            out_dir = infer_output_dir(args.chunks, args.out_dir)

        build_one_db(args.chunks, out_dir, emb, k_test=args.k_test)

    # ---------- 批量模式 ----------
    if args.chunks_dir:
        if not os.path.isdir(args.chunks_dir):
            raise NotADirectoryError(f"找不到 chunks 目录：{args.chunks_dir}")

        chunk_files = discover_chunk_files(args.chunks_dir)
        if not chunk_files:
            raise RuntimeError(f"在目录 {args.chunks_dir} 下没有发现 *_chunks.jsonl 文件")

        print(f"\n[Batch] found {len(chunk_files)} chunk files")
        for fp in chunk_files:
            out_dir = infer_output_dir(fp, args.out_dir)
            build_one_db(fp, out_dir, emb, k_test=args.k_test)

    print(f"\n{'=' * 70}")
    print("All done.")


if __name__ == "__main__":
    main()