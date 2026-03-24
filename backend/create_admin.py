import sys
import os
import logging

# 将后端目录加入寻址路径，确保能够顺利加载 app 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, Base, engine
from app.models.database import ServiceAgent
from app.utils.security import get_password_hash
from app.core.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - 🛡️ %(levelname)s - %(message)s",
)
logger = logging.getLogger("AdminInjector")


def ultimate_admin_override():
    """
    S级架构师注入脚本：完全脱离硬编码，通过 SQLAlchemy ORM 动态适配 MySQL/SQLite 等任何引擎
    """
    logger.info("=========================================================")
    logger.info("🚀 启动生产级物理表结构探针与管理员注入引擎...")

    # 1. 尝试初始化物理表结构 (幂等操作)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 底层 ORM 物理表结构元数据检查/同步通过。")
    except Exception as e:
        logger.error(f"❌ 致命错误：无法连接到数据库，请检查 DATABASE_URL 配置: {e}")
        return

    db = SessionLocal()
    try:
        # 2. 探针嗅探是否已存在 admin 账号
        target_username = "admin"
        existing_admin = (
            db.query(ServiceAgent)
            .filter(ServiceAgent.username == target_username)
            .first()
        )

        # 读取配置中的默认密码，若无则使用兜底密码
        admin_password = getattr(settings, "ADMIN_PASSWORD", "PoclainAdmin2026!")
        hashed_pwd = get_password_hash(admin_password)

        if existing_admin:
            logger.warning(
                f"⚠️ 探针发现已有管理员账号: {target_username}。正在执行强行覆写..."
            )
            existing_admin.password_hash = hashed_pwd
            # 重置离线状态，防止脏状态卡死
            existing_admin.status = "offline"
            existing_admin.is_active = True
            db.commit()

            logger.info("✅ 物理覆写成功！现存管理员密码已被重置。")
        else:
            logger.info("🔍 未发现管理员账号，正在执行强制物理注入...")
            new_admin = ServiceAgent(
                username=target_username,
                name="系统总架构师",
                password_hash=hashed_pwd,
                email="admin@poclain.com",
                phone="13800138000",
                status="offline",
                is_active=True,
                role="admin",
            )
            db.add(new_admin)
            db.commit()
            logger.info("✅ 暴力物理注入成功！已生成最高权限的根管理员。")

        logger.info("=========================================================")
        logger.info(f"👉 前端登录账号: {target_username}")
        logger.info(f"👉 前端登录密码: {admin_password}")
        logger.info("=========================================================")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 发生了未预期的底层 I/O 或约束异常: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    ultimate_admin_override()
