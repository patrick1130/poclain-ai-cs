import pandas as pd
import os
import logging
from typing import Optional

# 配置工业级日志记录
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def universal_excel_to_rag_text(
    input_file: str,
    output_file: str,
    primary_key_col: Optional[str] = None,
    sheet_name: int | str = 0,
):
    """
    通用 RAG 向量库语义平铺引擎 (Universal ETL Pipeline)

    算法复杂度: Big-O(N * M)，N为行数，M为列数。
    安全审计: 动态列嗅探、脏数据剥离、防空跑熔断。剥离了业务耦合，支持任意二维关系型数据源。

    :param input_file: 物理源文件路径 (.xlsx, .xls)
    :param output_file: 目标语料库文件路径 (.txt)
    :param primary_key_col: 实体主键列名。若为 None，将自动降级嗅探第一列作为主键。
    :param sheet_name: 指定读取的工作表，默认为 0（第一个表）。
    """
    try:
        if not os.path.exists(input_file):
            logger.error(f"致命错误: 源数据文件 {input_file} 物理路径不存在。")
            return

        logger.info(f"🚀 开始装载内存映射: {input_file} (Sheet: {sheet_name})")
        # 1. 物理读取 Excel 内存映射
        df = pd.read_excel(input_file, sheet_name=sheet_name)

        if df.empty:
            logger.warning("⚠️ 探测到空数据表，任务中止。")
            return

        # 清洗列名：剥离换行符与脏字符，确保维度 Key 绝对纯净
        df.columns = [str(col).strip().replace("\n", "") for col in df.columns]

        # 2. 动态主键路由探测
        if primary_key_col is None:
            # 自动降级：提取第一列作为默认主键锚点
            primary_key_col = df.columns[0]
            logger.info(
                f"🔍 未指定主键，系统自动嗅探第一列 [{primary_key_col}] 作为语义主锚点。"
            )
        elif primary_key_col not in df.columns:
            logger.error(
                f"❌ 索引越界: 指定的主键 [{primary_key_col}] 在数据表的表头中不存在。"
            )
            logger.info(f"可用表头: {list(df.columns)}")
            return

        results = []

        # 3. 遍历数据游标进行语义重构 (Semantic Flattening)
        for index, row in df.iterrows():
            # 锁定主键锚点数据
            anchor_value = str(row.get(primary_key_col, "")).strip()

            # 过滤无效空行 (NaN, None, 空字符串)
            if anchor_value == "nan" or anchor_value == "None" or not anchor_value:
                continue

            # 构建高密度语义向量锚点
            line_parts = [f"{primary_key_col}: {anchor_value}"]

            for col in df.columns:
                # 跳过主键列以防数据冗余
                if col == primary_key_col:
                    continue

                # 提取并清理维度值
                val = str(row[col]).strip()
                if val != "nan" and val != "None" and val != "NaT" and val:
                    line_parts.append(f"{col}: {val}")

            # 闭合知识边界，生成单条高内聚的 AI 记忆碎片
            full_line = "，".join(line_parts) + "。"
            results.append(full_line)

        # 4. 物理落盘 (持久化)
        if results:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n".join(results))
            logger.info(f"✅ ETL 转换完成！物理文件已安全生成: {output_file}")
            logger.info(f"📊 成功序列化有效高维数据行数: {len(results)}")
        else:
            logger.warning("⚠️ 过滤后无有效数据产出，未生成物理文件。")

    except Exception as e:
        logger.error(f"❌ 链路崩溃，I/O 或解析错误: {e}", exc_info=True)


# ==========================================
# 🚀 统一执行总线 (Execution Bus)
# ==========================================
if __name__ == "__main__":

    # 场景 1：清洗波克兰马达参数 (显式指定主键)
    # universal_excel_to_rag_text(
    #     input_file="poclain_motors_data.xlsx",
    #     output_file="knowledge_base_flattened.txt",
    #     primary_key_col="马达型号"
    # )

    # 场景 2：清洗通用数据表 (让系统自动识别第一列为主键)
    INPUT_FILE = "poclain_motors_data.xlsx"  # <--- 请在此处修改你的源文件名
    OUTPUT_FILE = "ai_corpus_output.txt"  # <--- 请在此处修改你的目标文件名

    # 创建一个测试文件检测逻辑 (可选)
    if not os.path.exists(INPUT_FILE):
        logger.warning(
            f"💡 提示: 请将你需要清洗的文件命名为 '{INPUT_FILE}' 并放在同级目录下。"
        )
    else:
        universal_excel_to_rag_text(
            input_file=INPUT_FILE,
            output_file=OUTPUT_FILE,
            # primary_key_col=None # 默认自动抓取第一列
        )
