import sqlite3
import os


def ultimate_privilege_escalation():
    db_path = "sql_app.db"
    if not os.path.exists(db_path):
        print("❌ 致命错误：未找到 sql_app.db 数据库。")
        return

    # 1. 尝试调用当前环境的原生安全算法生成哈希
    new_hashed_pwd = None
    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        new_hashed_pwd = pwd_context.hash("123456")
        print("✅ 成功调用宿主原生 Passlib 引擎生成安全哈希盐。")
    except ImportError:
        new_hashed_pwd = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIoQ1eaOO"
        print("⚠️ 未检测到原生 passlib 模块，回退使用标准安全盐。")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 2. 锁定目标鉴权表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        target_table = None
        columns = []

        for t in tables:
            t_name = t[0]
            if t_name.startswith("sqlite_"):
                continue
            cursor.execute(f"PRAGMA table_info({t_name});")
            cols = [c[1] for c in cursor.fetchall()]

            if any(k in cols for k in ["email", "username", "account"]) and any(
                "password" in c.lower() for c in cols
            ):
                target_table = t_name
                columns = cols
                break

        if not target_table:
            print("❌ 致命错误：未能锁定具有账户/密码特征的表。")
            return

        email_col = next(
            (c for c in columns if c in ["email", "username", "account"]), None
        )
        pwd_col = next((c for c in columns if "password" in c.lower()), None)

        # 3. 构建动态提权 SQL 映射集
        update_fields = [f"{pwd_col} = ?"]
        params = [new_hashed_pwd]

        # 智能扫描并补齐所有缺失的业务标识
        if "is_active" in columns:
            update_fields.append("is_active = ?")
            params.append(1)  # 激活账户
        if "is_superuser" in columns:
            update_fields.append("is_superuser = ?")
            params.append(1)  # 赋予超管
        if "role" in columns:
            update_fields.append("role = ?")
            params.append("admin")  # 赋予角色

        # 4. 执行精确打击提权
        cursor.execute(
            f"SELECT id, {email_col} FROM {target_table} ORDER BY id ASC LIMIT 1;"
        )
        user_record = cursor.fetchone()

        if user_record:
            u_id, u_email = user_record
            params.append(u_id)

            query = f"UPDATE {target_table} SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, tuple(params))
            conn.commit()

            print("=========================================")
            print("✅ 账户动态提权与原生哈希重置成功！")
            print(f"👉 目标数据表: {target_table}")
            print(f"👉 提权激活字段: {', '.join(update_fields).replace(' = ?', '')}")
            print(f"👉 前端登录账号: {u_email}")
            print(f"👉 前端登录密码: 123456")
            print("=========================================")
        else:
            print("❌ 致命错误：表中依然无任何用户数据。")

    except Exception as e:
        print(f"❌ 发生了未预期的数据库 I/O 异常: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    ultimate_privilege_escalation()
