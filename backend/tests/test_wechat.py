import requests
import time

# 🎯 目标靶机：你的 FastAPI 微信接收网关
# 注意：请确认你的真实微信 router 路径。通常是 /wechat 或 /api/v1/wechat
# 如果你后端的路径不同，请在这里修改：
TARGET_URL = "http://127.0.0.1:8000/api/v1/wechat"


def fire_mock_message():
    # 生成当前时间戳
    current_time = int(time.time())

    # 📝 完美伪造的微信底层 XML 报文
    xml_payload = f"""
    <xml>
      <ToUserName><![CDATA[gh_poclain_official]]></ToUserName>
      <FromUserName><![CDATA[Patrick_Test_User_888]]></FromUserName>
      <CreateTime>{current_time}</CreateTime>
      <MsgType><![CDATA[text]]></MsgType>
      <Content><![CDATA[你好！我是模拟客户。请问 Poclain MS18 液压马达的技术手册可以发我一份吗？]]></Content>
      <MsgId>{current_time}123456</MsgId>
    </xml>
    """

    print(f"🚀 [系统启动] 正在向 {TARGET_URL} 发射微信物理层模拟报文...")
    print(f"📦 [报文内容]: Poclain MS18 咨询请求")

    try:
        # 微信原生环境使用的是 text/xml 头部
        headers = {"Content-Type": "text/xml"}
        response = requests.post(
            TARGET_URL, data=xml_payload.encode("utf-8"), headers=headers
        )

        print(f"📡 [后端响应] 状态码: {response.status_code}")
        print(f"📩 [响应正文]: {response.text}")

        if response.status_code in [200, 201]:
            print("\n✅ [链路打通] 发射成功！现在立刻切回你的 Vue 浏览器窗口！")
            print("👁️  你应该能看到左侧列表弹出了名为 Patrick_Test_User_888 的新会话！")
        elif response.status_code == 404:
            print(
                "\n⚠️ [路径错误] 404 Not Found. Patrick，你的后端接收微信请求的路径叫什么？请修改代码里的 TARGET_URL。"
            )
        elif response.status_code == 422:
            print(
                "\n⚠️ [校验拦截] 422 Validation Error. 你的后端正在用 JSON 解析 XML，或者数据模型不匹配。"
            )

    except requests.exceptions.ConnectionError:
        print("\n❌ [连接失败] 无法连接到 8000 端口，请确认 Uvicorn 还在运行。")
    except Exception as e:
        print(f"\n❌ [未知异常] {e}")


if __name__ == "__main__":
    fire_mock_message()
