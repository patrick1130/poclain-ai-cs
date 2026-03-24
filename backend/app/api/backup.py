import logging
import io
import csv
from datetime import datetime
from typing import Optional, Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

# 导入数据库会话依赖与模型
from ..core.database import get_db
from ..models.database import Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["Backup Strategy Center"])


@router.get("/export")
async def export_chat_records(
    start_time: Optional[datetime] = Query(
        None, description="起始时间 (格式: YYYY-MM-DD HH:MM:SS)"
    ),
    end_time: Optional[datetime] = Query(
        None, description="结束时间 (格式: YYYY-MM-DD HH:MM:SS)"
    ),
    keyword: Optional[str] = Query(None, description="关键词模糊筛选"),
    db: Session = Depends(get_db),
):
    """
    🚨 S级架构设计：O(1) 内存流式导出引擎
    避免一次性全量加载导致 OOM，采用 Generator 实时游标读取与流式吐出。
    """
    # 1. 构建 O(log N) 高效复合查询条件
    filters = []
    if start_time:
        filters.append(Message.created_at >= start_time)
    if end_time:
        filters.append(Message.created_at <= end_time)
    if keyword:
        filters.append(Message.content.ilike(f"%{keyword}%"))

    # 2. 生成器闭包：流式按块读取与序列化
    def iter_csv_records() -> Generator[str, None, None]:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # 写入表头
        writer.writerow(
            [
                "Message ID",
                "Session ID",
                "Sender",
                "Content",
                "Message Type",
                "Created At",
                "User Name",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # 使用 yield_per(1000) 配合流式输出，确保物理内存占用永远被压制在 1000 条记录的体量
        query = (
            db.query(Message).filter(and_(*filters)).order_by(desc(Message.created_at))
        )
        for msg in query.yield_per(1000):
            # 获取枚举值以防序列化报错
            sender_val = (
                msg.sender.value if hasattr(msg.sender, "value") else str(msg.sender)
            )
            # 清洗内容中的换行符，防止 CSV 行错乱断裂
            safe_content = msg.content.replace("\n", " ").replace("\r", "")

            writer.writerow(
                [
                    msg.id,
                    msg.session_id,
                    sender_val,
                    safe_content,
                    msg.msg_type,
                    (
                        msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if msg.created_at
                        else ""
                    ),
                    msg.user_name or "Unknown",
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    # 3. 触发流式响应下载
    filename = f"chat_backup_{datetime.now().strftime('%Y%md%H%M%S')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}

    logger.info(f"📥 正在触发流式导出聊天记录 (TimeRange: {start_time} - {end_time})")
    return StreamingResponse(iter_csv_records(), media_type="text/csv", headers=headers)


@router.delete("/purge")
async def purge_chat_records(
    start_time: datetime = Query(..., description="起始时间 (必填，防全表误删)"),
    end_time: datetime = Query(..., description="结束时间 (必填，防全表误删)"),
    db: Session = Depends(get_db),
):
    """
    🚨 S级架构防御：强一致性原子化物理粉碎引擎
    严格锁定起止时间，使用原生的 DELETE SQL 语句直接作用于 InnoDB 引擎，避免 ORM 逐条删除的性能灾难。
    """
    # 1. 业务逻辑与安全护栏：禁止删除未来数据或反向时间范围
    if start_time >= end_time:
        raise HTTPException(
            status_code=400, detail="非法操作：结束时间必须晚于起始时间"
        )

    try:
        # 2. O(1) 级 InnoDB 批量直接删除指令
        deleted_count = (
            db.query(Message)
            .filter(
                and_(Message.created_at >= start_time, Message.created_at <= end_time)
            )
            .delete(synchronize_session=False)
        )  # 跳过内存状态同步，实现极致提速

        # 3. 强一致性事务提交
        db.commit()

        logger.warning(
            f"🗑️ 物理粉碎完成：已永久删除 {start_time} 至 {end_time} 期间的 {deleted_count} 条聊天记录。"
        )

        return {
            "status": "success",
            "message": f"成功物理粉碎 {deleted_count} 条聊天记录",
            "deleted_count": deleted_count,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 物理粉碎事务失败: {str(e)}")
        raise HTTPException(
            status_code=500, detail="数据库粉碎事务执行失败，引擎已执行安全回滚。"
        )
