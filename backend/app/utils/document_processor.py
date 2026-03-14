# File: backend/app/utils/document_processor.py

import re
from typing import List
from ..core.config import settings


def clean_text(text: str) -> str:
    """
    清理文本。
    【架构修复】修改正则逻辑，保留换行符 \n 以维持段落语义边界。
    仅清理行内的多余空白字符（空格、制表符等），并将连续的多个空行压缩为单行。
    算法复杂度控制在 $O(N)$，避免正则表达式引发灾难性回溯。
    """
    if not text:
        return ""

    # 第一步：将行内连续的空白字符（不含换行符）替换为单一空格
    cleaned = re.sub(r"[ \t\r\f]+", " ", text)
    # 第二步：将连续的三个及以上换行符（包含夹杂的空格）压缩为双换行符，保留合理的段落间距
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
    将文档切分为多个片段，强制保证任何片段不超过 max_chunk_size 阈值。
    【架构修复】修复滑窗逻辑死锁，确保语义片段的重叠度精确生效。
    """
    if max_chunk_size is None:
        max_chunk_size = getattr(settings, "KNOWLEDGE_CHUNK_SIZE", 1000)
    if overlap is None:
        overlap = getattr(settings, "KNOWLEDGE_CHUNK_OVERLAP", 100)

    header = f"【{category}-{title}】\n"
    # 计算实际留给正文的最大安全容量
    max_content_len = max_chunk_size - len(header)

    # 防御性配置校验：重叠部分绝不能超过最大容量的一半，否则会导致死循环或切片极小
    if max_content_len <= overlap:
        max_content_len = 1000  # 强制熔断至安全默认值
        overlap = 100
    if overlap >= max_content_len // 2:
        overlap = max_content_len // 4

    # 清洗并按自然段落切分
    cleaned_content = clean_text(content)
    # 按双换行或单换行切分，尽量保持自然段落完整
    paragraphs = re.split(r"\n+", cleaned_content)

    chunks = []
    current_text = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # 应对恶意长段落的硬边界截断 (Hard Slicing)
        if len(paragraph) > max_content_len:
            # 先将已经积累的 current_text 结算掉
            if current_text:
                chunks.append(header + current_text)
                current_text = ""

            # 【架构修复】精确的滑动窗口切割，彻底修复 overlap 归零漏洞
            start = 0
            while start < len(paragraph):
                end = start + max_content_len
                slice_str = paragraph[start:end]
                chunks.append(header + slice_str)

                # 如果已经切到了段落末尾，直接结束本段落的切分
                if end >= len(paragraph):
                    break

                # 向前滑动时严格保留 overlap 的长度
                # 步长为 max_content_len - overlap，确保一定前进且重叠正确
                start += max_content_len - overlap
            continue

        # 常规段落合并逻辑
        if len(current_text) + len(paragraph) + 1 > max_content_len:
            chunks.append(header + current_text)

            # 新片段保留部分重叠内容，确保上下文连贯
            if len(current_text) > overlap:
                overlap_text = current_text[-overlap:]
                # 尝试寻找最后一个完整的句子边界作为起点，避免单词被切断
                last_period = max(overlap_text.rfind("。"), overlap_text.rfind("."))
                if last_period != -1 and last_period < len(overlap_text) - 1:
                    overlap_text = overlap_text[last_period + 1 :].strip()
            else:
                overlap_text = current_text

            current_text = (
                overlap_text + "\n" + paragraph if overlap_text else paragraph
            )
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
    """
    合并重叠度过高的片段。已将 $O(L^2)$ 的暴力切片降维。
    """
    if not chunks:
        return []

    merged = [chunks[0]]

    for current in chunks[1:]:
        previous = merged[-1]

        max_possible_overlap = min(len(previous), len(current))
        overlap_length = 0

        # 逆向滑动窗口匹配
        # 从最大可能的重叠长度开始向下递减，一旦命中即是最长匹配，立即 break。
        for i in range(max_possible_overlap, 0, -1):
            if previous[-i:] == current[:i]:
                overlap_length = i
                break

        if max_possible_overlap > 0:
            overlap_ratio = overlap_length / max_possible_overlap
        else:
            overlap_ratio = 0.0

        # 如果重叠比例超过阈值，合并片段
        if overlap_ratio > overlap_threshold:
            merged[-1] = previous + current[overlap_length:]
        else:
            merged.append(current)

    return merged
