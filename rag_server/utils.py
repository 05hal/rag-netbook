from typing import List

from models import SourceItem


def should_skip_doc(path: str) -> bool:
    bad_words = ["附录", "参考文献", "习题答案", "索引"]
    return any(x in path for x in bad_words)


def build_sources(docs: List) -> List[SourceItem]:
    sources = []
    for doc in docs:
        sources.append(
            SourceItem(
                chapter=str(doc.metadata.get("chapter", "")),
                path=str(doc.metadata.get("path", "")),
                chunk_id=str(doc.metadata.get("chunk_id", "")),
                content=doc.page_content[:300],
            )
        )
    return sources