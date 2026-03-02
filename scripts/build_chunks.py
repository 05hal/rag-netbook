# scripts/chunk_docx.py
# pip install python-docx

import os
import re
import json
import html
import argparse
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from docx import Document


# -------------------------
# 默认配置（可通过命令行参数覆盖）
# -------------------------
DEFAULT_MAX_CHARS = 900
DEFAULT_OVERLAP = 80
DEFAULT_MAX_SECTION_CHARS = 30000


@dataclass
class Chunk:
    text: str
    meta: Dict


def is_heading_style(style_name: str) -> Optional[int]:
    """识别 Word 标题样式层级（中英文通用）。"""
    if not style_name:
        return None
    name = style_name.strip().lower()

    # 英文 Heading
    if "heading 1" in name:
        return 1
    if "heading 2" in name:
        return 2
    if "heading 3" in name:
        return 3
    if "heading 4" in name:
        return 4

    # 中文 标题
    if name in ["标题 1", "标题1"]:
        return 1
    if name in ["标题 2", "标题2"]:
        return 2
    if name in ["标题 3", "标题3"]:
        return 3
    if name in ["标题 4", "标题4"]:
        return 4

    return None


# 编号标题补救（当 Word 没用标题样式时）
RE_NUM_H2 = re.compile(r"^\s*\d+\.\d+\s+.+")              # 1.2 xxx
RE_NUM_H3 = re.compile(r"^\s*\d+\.\d+\.\d+\s+.+")         # 1.2.3 xxx
RE_CHAPTER = re.compile(r"^\s*第\s*\d+\s*章")              # 第1章
RE_CN_ENUM = re.compile(r"^\s*[（(][一二三四五六七八九十]+[）)]\s*.+")  # （一）xxx
RE_DOT_ENUM = re.compile(r"^\s*\d+\s*[\.、]\s*.+")         # 1. xxx / 1、xxx


def infer_heading_level_by_text(text: str) -> Optional[int]:
    """
    仅用于补救：当 style 不是标题，但文本像标题时，给一个推断层级。
    可按教材风格继续扩展。
    """
    t = text.strip()

    if RE_CHAPTER.match(t):
        return 1
    if RE_NUM_H3.match(t):
        return 3
    if RE_NUM_H2.match(t):
        return 2
    if RE_CN_ENUM.match(t):
        return 4
    if RE_DOT_ENUM.match(t):
        return 4

    return None


def split_text_natural(text: str, max_chars: int, overlap: int) -> List[str]:
    """
    教材友好切块：优先按句号/换行切，超长再硬切。
    """
    text = (text or "").strip()
    if not text:
        return []
    if overlap >= max_chars:
        overlap = max_chars // 5

    segs = re.split(r'(\n+|。|！|？|；)', text)
    pieces = []
    buf = ""

    for s in segs:
        if not s:
            continue
        candidate = buf + s
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf.strip():
                pieces.append(buf.strip())
            buf = s.strip()

            # 单片段仍过长 → 硬切
            while len(buf) > max_chars:
                pieces.append(buf[:max_chars].strip())
                buf = buf[max_chars - overlap:].strip()

    if buf.strip():
        pieces.append(buf.strip())

    # overlap 连接
    out = []
    for i, p in enumerate(pieces):
        if i == 0:
            out.append(p)
        else:
            prefix = out[-1][-overlap:] if len(out[-1]) > overlap else out[-1]
            out.append((prefix + p).strip())

    return [x for x in out if x]


def make_html_report(docx_name: str, paras_info: List[Dict], chunks: List[Chunk], out_path: str):
    """输出可视化切块依据 HTML 报告。"""
    boundary_by_start = {}
    for c in chunks:
        sp = c.meta.get("start_para")
        if sp is not None:
            boundary_by_start.setdefault(sp, []).append(c)

    lines = []
    lines.append("<html><head><meta charset='utf-8'>")
    lines.append("<style>")
    lines.append("body{font-family:Arial,'Microsoft YaHei'; line-height:1.45;}")
    lines.append(".para{padding:6px 8px; border-bottom:1px solid #eee;}")
    lines.append(".tag{display:inline-block; padding:2px 6px; border-radius:6px; background:#f3f3f3; margin-right:6px; font-size:12px;}")
    lines.append(".chunkbar{margin:14px 0; padding:10px; border:2px solid #333; background:#fafafa;}")
    lines.append(".meta{font-size:12px; color:#444; margin-top:4px;}")
    lines.append("</style></head><body>")
    lines.append(f"<h2>Chunk 可视化报告：{html.escape(docx_name)}</h2>")
    lines.append("<p>粗框表示一个 chunk 的开始；每段落显示 style 与推断层级。</p>")

    for p in paras_info:
        idx = p["idx"]
        if idx in boundary_by_start:
            for c in boundary_by_start[idx]:
                lines.append("<div class='chunkbar'>")
                lines.append(f"<b>CHUNK {html.escape(str(c.meta.get('chunk_id')))} | {html.escape(str(c.meta.get('path')))}</b>")
                lines.append("<div class='meta'>"
                             f"段落范围：{c.meta.get('start_para')} ~ {c.meta.get('end_para')} | "
                             f"字符数：{c.meta.get('chars')} | "
                             f"h1={c.meta.get('h1')} / h2={c.meta.get('h2')} / h3={c.meta.get('h3')} / h4={c.meta.get('h4')}"
                             "</div>")
                lines.append("</div>")

        lines.append("<div class='para'>"
                     f"<span class='tag'>P{idx}</span>"
                     f"<span class='tag'>{html.escape(p['tag'])}</span>"
                     f"<span class='tag'>style: {html.escape(p['style'])}</span>"
                     f"<span class='tag'>infer: {html.escape(str(p['inferred_level']))}</span>"
                     f"{html.escape(p['text'])}"
                     "</div>")

    lines.append("</body></html>")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build_chunks_from_docx(docx_path: str, max_chars: int, overlap: int, max_section_chars: int) -> Tuple[List[Chunk], List[Dict]]:
    doc = Document(docx_path)

    # 标题路径
    h = {1: None, 2: None, 3: None, 4: None}

    section_buffer: List[str] = []
    section_paras_idx: List[int] = []
    section_meta: Dict = {"h1": None, "h2": None, "h3": None, "h4": None, "path": ""}

    chunks: List[Chunk] = []
    section_counter = 0
    paras_info = []

    def current_path():
        return " > ".join([x for x in [h[1], h[2], h[3], h[4]] if x])

    def flush_section():
        nonlocal section_counter, section_buffer, section_meta, chunks, section_paras_idx
        if not section_buffer:
            section_buffer = []
            section_paras_idx = []
            return

        content = "\n".join([x.strip() for x in section_buffer if x.strip()]).strip()
        if not content:
            section_buffer = []
            section_paras_idx = []
            return

        parts = split_text_natural(content, max_chars=max_chars, overlap=overlap)
        start_para = section_paras_idx[0] if section_paras_idx else None
        end_para = section_paras_idx[-1] if section_paras_idx else None

        for idx, part in enumerate(parts):
            meta = dict(section_meta)
            meta.update({
                "chunk_index_in_section": idx,
                "chunk_id": f"{section_counter:04d}-{idx:02d}",
                "source": os.path.basename(docx_path),
                "chars": len(part),
                "start_para": start_para,
                "end_para": end_para,
            })
            chunks.append(Chunk(text=part, meta=meta))

        section_counter += 1
        section_buffer = []
        section_paras_idx = []

    for p_idx, p in enumerate(doc.paragraphs):
        text = (p.text or "").strip()
        style_name = p.style.name if p.style else ""

        if not text:
            continue

        level = is_heading_style(style_name)
        inferred = None
        if level is None:
            inferred = infer_heading_level_by_text(text)

        tag = "BODY"
        if level is not None:
            tag = f"H{level}"
        elif inferred is not None:
            tag = f"INFER_H{inferred}"

        paras_info.append({
            "idx": p_idx,
            "style": style_name,
            "inferred_level": inferred,
            "tag": tag,
            "text": text
        })

        final_level = level if level is not None else inferred

        if final_level is not None:
            flush_section()

            h[final_level] = text
            for lv in range(final_level + 1, 5):
                h[lv] = None

            section_meta = {
                "h1": h[1],
                "h2": h[2],
                "h3": h[3],
                "h4": h[4],
                "path": current_path(),
                "title_level": final_level,
                "title_text": text,
                "title_para_index": p_idx,
            }
        else:
            section_buffer.append(text)
            section_paras_idx.append(p_idx)

            if sum(len(x) for x in section_buffer) > max_section_chars:
                flush_section()

    flush_section()
    return chunks, paras_info


def save_chunks_jsonl(chunks: List[Chunk], out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps({"text": c.text, "meta": c.meta}, ensure_ascii=False) + "\n")


def print_stats(jsonl_path: str):
    lens = []
    paths = {}
    n = 0
    max_depth = 0
    depth_hist = {1: 0, 2: 0, 3: 0, 4: 0}

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            text = obj["text"]
            meta = obj["meta"]
            lens.append(len(text))

            p = meta.get("path", "")
            paths[p] = paths.get(p, 0) + 1

            depth = 0
            for k in ["h1", "h2", "h3", "h4"]:
                if meta.get(k):
                    depth += 1
            max_depth = max(max_depth, depth)
            if depth > 0:
                depth_hist[depth] = depth_hist.get(depth, 0) + 1

            n += 1

    print("chunks:", n)
    print("len(min/avg/max):", min(lens), sum(lens)//len(lens), max(lens))
    print("unique paths:", len(paths))
    print("max title depth:", max_depth)
    print("depth hist:", depth_hist)


def main():
    parser = argparse.ArgumentParser(description="通用 DOCX 教材切块器（输出 jsonl + html 可视化）")
    parser.add_argument("docx_path", help="输入 docx 路径，例如 data/chapter1.docx")
    parser.add_argument("--out_dir", default="chunks", help="输出目录（默认 chunks/）")
    parser.add_argument("--max_chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument("--max_section_chars", type=int, default=DEFAULT_MAX_SECTION_CHARS)
    args = parser.parse_args()

    docx_path = args.docx_path
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"找不到文件：{docx_path}")

    os.makedirs(args.out_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(docx_path))[0]
    out_jsonl = os.path.join(args.out_dir, f"{base}_chunks.jsonl")
    out_html = os.path.join(args.out_dir, f"{base}_chunk_report.html")

    chunks, paras_info = build_chunks_from_docx(
        docx_path,
        max_chars=args.max_chars,
        overlap=args.overlap,
        max_section_chars=args.max_section_chars
    )

    save_chunks_jsonl(chunks, out_jsonl)
    make_html_report(os.path.basename(docx_path), paras_info, chunks, out_html)

    print("已输出：")
    print(" -", out_jsonl)
    print(" -", out_html)

    print_stats(out_jsonl)


if __name__ == "__main__":
    main()