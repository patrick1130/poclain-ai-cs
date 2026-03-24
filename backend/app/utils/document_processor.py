import os
import uuid
import fitz  # PyMuPDF
import logging
import asyncio
import re
from typing import List
from dashscope import MultiModalConversation
from ..core.config import settings

logger = logging.getLogger(__name__)

# ==========================================
# 1. 视觉解析引擎
# ==========================================


class MultimodalDocumentParser:
    def __init__(self):
        # 确保阿里云 API Key 已配置
        if not settings.DASHSCOPE_API_KEY:
            raise ValueError("🚨 致命错误: 未配置 DASHSCOPE_API_KEY")
        import dashscope

        dashscope.api_key = settings.DASHSCOPE_API_KEY

        # 创建临时图片存放目录
        self.temp_dir = os.path.join(os.getcwd(), "backend", "temp_images")
        os.makedirs(self.temp_dir, exist_ok=True)

    async def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        """
        将 PDF 逐页转换为高清图片，并调用 Qwen-VL-Max 进行视觉解析，最终合并为完整的 Markdown
        """
        logger.info(f"📄 开始视觉解析 PDF: {pdf_path}")

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"找不到文件: {pdf_path}")

        doc = fitz.open(pdf_path)
        full_markdown = []

        # 🚨 架构师修正：生成本次解析任务的唯一事务 ID，实现并发物理隔离
        transaction_id = uuid.uuid4().hex

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 提升分辨率 (2.0 zoom 约等于 144 DPI)，保证液压曲线图和表格清晰可见
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 🚨 架构师修正：引入唯一命名空间，防止 Race Condition 导致的跨租户数据污染
            temp_img_path = os.path.join(
                self.temp_dir, f"page_{transaction_id}_{page_num + 1}.jpg"
            )

            try:
                # 物理落盘
                pix.save(temp_img_path)

                logger.info(
                    f"👁️ 正在利用 Qwen-VL-Max 读取第 {page_num + 1}/{len(doc)} 页..."
                )

                page_md = await self._analyze_image_with_vl(temp_img_path, page_num + 1)
                full_markdown.append(page_md)

            finally:
                # 🚨 架构师修正：确立绝对的安全铁律，无论 API 是否崩溃，必须销毁物理切片，防范磁盘耗尽
                if os.path.exists(temp_img_path):
                    try:
                        os.remove(temp_img_path)
                    except Exception as e:
                        logger.error(
                            f"⚠️ 致命：临时文件销毁失败 (PID: {os.getpid()}): {e}"
                        )

        doc.close()
        logger.info(f"✅ PDF 视觉解析完成，共生成 {len(full_markdown)} 页 Markdown。")

        # 将所有页面的 Markdown 用双换行符拼接
        return "\n\n".join(full_markdown)

    async def _analyze_image_with_vl(self, image_path: str, page_num: int) -> str:
        """调用阿里云千亿视觉大模型提取文本、表格和解释液压曲线"""

        # 🚨 钢铁苍穹：注入针对 Poclain 手册的 Pro 级视觉指令
        prompt = f"""
        你是一位资深的 Poclain (波克兰液压) 工程师。请精确提取这张技术手册扫描件（第 {page_num} 页）上的所有内容，并转化为标准 Markdown 格式。
        
        严格遵守以下规则：
        1. **表格处理**：遇到参数表格，必须使用 `|---|---|` 的严格 Markdown 表格语法还原。绝不能让列数据错位。
        2. **曲线图处理 (核心)**：如果页面中存在性能曲线图（如排量/扭矩/压力曲线），请在 Markdown 中插入一段文本描述，例如：“【性能曲线分析】：该图展示了XX马达的性能，横轴为XX，纵轴为XX。当压力达到XX时，输出扭矩为XX...”。
        3. **排版还原**：保留原有的各级标题（使用 `#`, `##`, `###`），确保段落清晰。
        4. **禁止编造**：只输出图片上看到的内容，如果图片是空白页，直接输出“（空白页）”。
        """

        messages = [
            {
                "role": "user",
                "content": [
                    {"image": f"file://{image_path}"},
                    {"text": prompt},
                ],
            }
        ]

        try:
            response = await asyncio.to_thread(
                MultiModalConversation.call,
                model="qwen-vl-max",
                messages=messages,
            )

            if response.status_code == 200:
                raw_content = response.output.choices[0].message.content
                if isinstance(raw_content, list):
                    extracted_text = "\n".join(
                        [
                            item.get("text", "")
                            for item in raw_content
                            if isinstance(item, dict) and "text" in item
                        ]
                    )
                    return extracted_text
                elif isinstance(raw_content, str):
                    return raw_content
                else:
                    return str(raw_content)
            else:
                logger.error(
                    f"第 {page_num} 页解析失败: Code: {response.code}, Msg: {response.message}"
                )
                return f"\n\n> [警告：第 {page_num} 页视觉解析失败]\n\n"
        except Exception as e:
            logger.error(f"第 {page_num} 页触发异常: {e}")
            return f"\n\n> [警告：第 {page_num} 页发生引擎崩溃]\n\n"


# ==========================================
# 2. 文本清洗与切片引擎 (🚨 表头吸附重构)
# ==========================================


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
    🚨 架构师重构：Header-Aware Tabular Chunking (表头感知切片引擎)
    弃用粗暴的段落切割，改用行级状态机。保证 Markdown 表格在被切断时，
    表头属性会像基因一样复制并吸附到每一个表格碎片的顶部，彻底消灭列错位致幻。
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

    cleaned_content = clean_text(content)
    lines = cleaned_content.split("\n")

    chunks = []
    current_chunk_lines = []
    current_length = 0

    # 表格状态机寄存器
    in_table = False
    table_header_cache = []

    for line in lines:
        line_len = len(line) + 1  # 包含换行符
        stripped_line = line.strip()

        # 1. 状态机：探测与捕获 Markdown 表头
        is_table_row = stripped_line.startswith("|") and stripped_line.endswith("|")

        if is_table_row:
            if not in_table:
                in_table = True
                table_header_cache = [line]  # 捕获表头第一行 (列名)
            elif len(table_header_cache) == 1:
                # 捕获表头第二行 (格式控制符如 |---|---| )
                if re.match(r"^\|[\s\-\|:]+\|$", stripped_line):
                    table_header_cache.append(line)
                else:
                    pass  # 不是标准分隔符，跳过缓存
        else:
            in_table = False
            table_header_cache = []

        # 2. 块容量检测与物理结算
        if current_length + line_len > max_content_len and current_chunk_lines:
            # 当前块已满，落盘结算
            chunks.append(header + "\n".join(current_chunk_lines))

            # 提取 Overlap 重叠部分，保证上下文平滑过渡
            overlap_lines = []
            overlap_len = 0
            for prev_line in reversed(current_chunk_lines):
                if overlap_len + len(prev_line) + 1 > overlap:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_len += len(prev_line) + 1

            current_chunk_lines = overlap_lines
            current_length = overlap_len

            # 🚨 架构师防熔断补丁：如果切断刚好发生在表格内部，强行注入表头！
            if in_table and len(table_header_cache) >= 1:
                header_str = "\n".join(table_header_cache)
                overlap_str = "\n".join(overlap_lines)

                # 防止由于 overlap 已经包含了表头而导致的重复注入
                if header_str not in overlap_str:
                    current_chunk_lines = table_header_cache + current_chunk_lines
                    current_length += sum(len(h) + 1 for h in table_header_cache)

        # 3. 正常追加当前行
        current_chunk_lines.append(line)
        current_length += line_len

    # 结算文档尾部最后一个残留块
    if current_chunk_lines:
        chunks.append(header + "\n".join(current_chunk_lines))

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

        # O(L) 级滑动窗口匹配
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
