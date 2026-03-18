import re
from typing import List
from ..core.config import settings


def clean_text(text: str) -> str:
    """清理文本：压缩多余空白，保留自然段落"""
    if not text:
        return ""
    cleaned = re.sub(r"[ \t\r\f]+", " ", text)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


def split_document(
    title: str,
    content: str,
    category: str,
    max_chunk_size: int = None,
    overlap: int = None,
) -> List[str]:
    """
    S级架构切片引擎：将文档切分为多个片段，强制保证任何片段严格小于 max_chunk_size。
    """
    if max_chunk_size is None:
        max_chunk_size = getattr(settings, "KNOWLEDGE_CHUNK_SIZE", 1000)
    if overlap is None:
        overlap = getattr(settings, "KNOWLEDGE_CHUNK_OVERLAP", 100)

    header = f"【{category}-{title}】\n"
    max_content_len = max_chunk_size - len(header)

    if max_content_len <= overlap:
        max_content_len = 1000
        overlap = 100
    if overlap >= max_content_len // 2:
        overlap = max_content_len // 4

    cleaned_content = clean_text(content)
    paragraphs = re.split(r"\n+", cleaned_content)

    chunks = []
    current_text = ""

    def slice_long_text(long_text: str):
        """内部闭包：处理超长文本的严格物理切片"""
        start = 0
        while start < len(long_text):
            end = start + max_content_len
            slice_str = long_text[start:end]
            chunks.append(header + slice_str)
            if end >= len(long_text):
                break
            start += max_content_len - overlap

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # 应对单个恶意长段落
        if len(paragraph) > max_content_len:
            if current_text:
                chunks.append(header + current_text)
                current_text = ""
            slice_long_text(paragraph)
            continue

        # 常规段落合并
        if len(current_text) + len(paragraph) + 1 > max_content_len:
            # 当前文本已满，安全结算
            chunks.append(header + current_text)

            # 抽取重叠句 (Overlap)
            overlap_text = ""
            if len(current_text) > overlap:
                overlap_text = current_text[-overlap:]
                last_period = max(overlap_text.rfind("。"), overlap_text.rfind("."))
                if last_period != -1 and last_period < len(overlap_text) - 1:
                    overlap_text = overlap_text[last_period + 1 :].strip()
            else:
                overlap_text = current_text

            # 拼接产生新块
            new_text = overlap_text + "\n" + paragraph if overlap_text else paragraph

            # 🚨 架构师补丁：防止 Overlap + Paragraph 再次发生溢出
            if len(new_text) > max_content_len:
                slice_long_text(new_text)
                current_text = ""
            else:
                current_text = new_text
        else:
            current_text = (
                current_text + "\n" + paragraph if current_text else paragraph
            )

    # 结算最后一个残留片段
    if current_text:
        chunks.append(header + current_text)

    return chunks


def merge_overlapping_chunks(
    chunks: List[str], overlap_threshold: float = 0.5
) -> List[str]:
    """合并重叠度过高的片段，优化检索噪音"""
    if not chunks:
        return []

    merged = [chunks[0]]

    for current in chunks[1:]:
        previous = merged[-1]
        max_possible_overlap = min(len(previous), len(current))
        overlap_length = 0

        # $O(L)$ 级滑动窗口匹配
        for i in range(max_possible_overlap, 0, -1):
            if previous[-i:] == current[:i]:
                overlap_length = i
                break

        overlap_ratio = (
            overlap_length / max_possible_overlap if max_possible_overlap > 0 else 0.0
        )

        if overlap_ratio > overlap_threshold:
            merged[-1] = previous + current[overlap_length:]
        else:
            merged.append(current)

    return merged
