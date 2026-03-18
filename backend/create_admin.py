import sqlite3
import os


def ultimate_admin_override():
    db_path = "sql_app.db"
    if not os.path.exists(db_path):
        print(
            "❌ 致命错误：当前目录下根本不存在 sql_app.db 文件。你的后端可能尚未触发建表，或运行在不同目录。"
        )
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 第一阶段：提取全部物理表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(
                "❌ 致命错误：sql_app.db 是一个 0kb 的空库。底层 ORM 根本没有执行物理建表。"
            )
            print(
                "👉 指导意见：你可能需要先停止后端，执行 alembic upgrade head 或确保 FastAPI 触发了元数据创建逻辑。"
            )
            return

        print("🔍 启动物理表结构深度嗅探...")
        target_table = None
        email_col = None
        pwd_col = None

        # 第二阶段：根据字段特征锁定用户表
        for table_tuple in tables:
            t_name = table_tuple[0]
            if t_name.startswith("sqlite_"):
                continue

            cursor.execute(f"PRAGMA table_info({t_name});")
            columns = cursor.fetchall()
            col_names = [col[1] for col in columns]
            print(f"  -> 探测到物理表: {t_name} | 包含字段: {col_names}")

            has_account = any(
                keyword in col_names for keyword in ["email", "username", "account"]
            )
            has_pwd = any("password" in c.lower() for c in col_names)

            if has_account and has_pwd:
                target_table = t_name
                email_col = next(
                    (c for c in col_names if c in ["email", "username", "account"]),
                    None,
                )
                pwd_col = next((c for c in col_names if "password" in c.lower()), None)

        if not target_table:
            print(
                "❌ 致命错误：全库扫描完毕，没有任何表结构同时包含用户账户和密码字段。"
            )
            return

        print(f"\n🎯 成功锁定鉴权核心表：{target_table}")

        # 第三阶段：提取首行数据或强行注入
        cursor.execute(f"SELECT id, {email_col} FROM {target_table} LIMIT 1;")
        user_record = cursor.fetchone()

        # 对应明文 "123456" 的合法 Bcrypt 签名
        new_hashed_pwd = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIoQ1eaOO"

        if user_record:
            u_id, u_email = user_record
            cursor.execute(
                f"UPDATE {target_table} SET {pwd_col} = ? WHERE id = ?",
                (new_hashed_pwd, u_id),
            )
            conn.commit()
            print("=========================================")
            print("✅ 物理覆盖执行成功！现存管理员密码已被强行重置。")
            print(f"👉 前端登录账号: {u_email}")
            print(f"👉 前端登录密码: 123456")
            print("=========================================")
        else:
            print(f"⚠️ 警告：{target_table} 表中无任何记录。正在执行强制物理注入...")
            try:
                cursor.execute(
                    f"INSERT INTO {target_table} ({email_col}, {pwd_col}) VALUES (?, ?)",
                    ("admin@poclain.com", new_hashed_pwd),
                )
                conn.commit()
                print("=========================================")
                print("✅ 暴力物理注入成功！已生成最高权限的根管理员。")
                print(f"👉 前端登录账号: admin@poclain.com")
                print(f"👉 前端登录密码: 123456")
                print("=========================================")
            except Exception as e:
                print(f"❌ 强行注入失败，可能被底层约束拦截: {e}")

    except Exception as e:
        print(f"❌ 发生了未预期的底层 I/O 异常: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    ultimate_admin_override()
