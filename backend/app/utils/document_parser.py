"""
Poclain 智能客服 - 多模态 PDF 视觉解析器 (S 级)
基于 PyMuPDF + 阿里云 Qwen-VL-Max 视觉大模型
"""

import os
import fitz  # PyMuPDF
import logging
import asyncio
from typing import List
from dashscope import MultiModalConversation
from ..core.config import settings

logger = logging.getLogger(__name__)


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

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)

            # 提升分辨率 (2.0 zoom 约等于 144 DPI)，保证液压曲线图和表格清晰可见
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 临时保存图片给视觉大模型读取
            temp_img_path = os.path.join(self.temp_dir, f"page_{page_num + 1}.jpg")
            pix.save(temp_img_path)

            logger.info(
                f"👁️ 正在利用 Qwen-VL-Max 读取第 {page_num + 1}/{len(doc)} 页..."
            )

            page_md = await self._analyze_image_with_vl(temp_img_path, page_num + 1)
            full_markdown.append(page_md)

            # 解析完毕后清理临时图片
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

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
                    # DashScope Python SDK 支持直接读取本地文件 URL
                    {"image": f"file://{image_path}"},
                    {"text": prompt},
                ],
            }
        ]

        try:
            # 使用 asyncio.to_thread 将同步的 DashScope SDK 调用包装为异步
            response = await asyncio.to_thread(
                MultiModalConversation.call,
                model="qwen-vl-max",  # 使用最强视觉模型，看懂复杂曲线图
                messages=messages,
            )

            if response.status_code == 200:
                raw_content = response.output.choices[0].message.content

                # 🚨 架构师补丁：处理多模态模型特殊的 List 返回结构
                if isinstance(raw_content, list):
                    # 抽取所有包含 'text' 的块并拼接
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
