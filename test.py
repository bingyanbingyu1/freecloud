import os
import cloudscraper
import logging
from typing import Optional
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# 环境变量
USERNAME = os.getenv("FC_USERNAME")
PASSWORD = os.getenv("FC_PASSWORD")
MACHINE_ID = os.getenv("FC_MACHINE_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

if not all([USERNAME, PASSWORD, MACHINE_ID]):
    logging.error("环境变量 FC_USERNAME / FC_PASSWORD / FC_MACHINE_ID 缺失，请配置后重试。")
    exit(1)

# URL 定义
LOGIN_URL = "https://freecloud.ltd/login"
CONSOLE_URL = "https://freecloud.ltd/member/index"
RENEW_URL = f"https://freecloud.ltd/server/detail/{MACHINE_ID}/renew"

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://freecloud.ltd/login",
    "Origin": "https://freecloud.ltd",
    "Content-Type": "application/x-www-form-urlencoded"
}

LOGIN_PAYLOAD = {
    "username": USERNAME,
    "password": PASSWORD,
    "mobile": "",
    "captcha": "",
    "verify_code": "",
    "agree": "1",
    "login_type": "PASS",
    "submit": "1",
}

RENEW_PAYLOAD = {
    "month": "1",
    "submit": "1",
    "coupon_id": 0
}


def send_telegram_message(message: str) -> None:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        logging.warning("⚠️ 未配置 TG_BOT_TOKEN / TG_CHAT_ID，无法推送消息。")
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            logging.warning(f"⚠️ Telegram 消息推送失败: {response.text}")
    except Exception as e:
        logging.exception("❌ 推送 Telegram 消息异常：")


def login_session() -> Optional[cloudscraper.CloudScraper]:
    logging.info("🚀 正在尝试登录 FreeCloud...")
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    try:
        resp = scraper.post(LOGIN_URL, data=LOGIN_PAYLOAD, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()

        if "退出登录" not in resp.text and "member/index" not in resp.text:
            logging.error("❌ 登录失败，请检查用户名或密码是否正确。")
            send_telegram_message("❌ 登录失败，请检查 FreeCloud 用户名或密码是否正确。")
            return None

        # 访问控制台保持会话
        scraper.get(CONSOLE_URL, headers=HEADERS)
        logging.info("✅ 登录成功！")
        send_telegram_message("✅ FreeCloud 登录成功！")
        return scraper

    except Exception as e:
        logging.exception("❌ 登录过程中发生错误：")
        send_telegram_message(f"❌ 登录出错：{str(e)}")
        return None


def renew_server(session: cloudscraper.CloudScraper) -> None:
    logging.info(f"🔄 正在尝试为服务器 {MACHINE_ID} 续费...")
    try:
        response = session.post(RENEW_URL, data=RENEW_PAYLOAD, headers=HEADERS)
        response.raise_for_status()

        try:
            data = response.json()
            msg = data.get("msg", "")
            if msg == '请在到期前3天后再续费':
                logging.warning(f"⚠️ 续费状态：{msg}")
                send_telegram_message(f"⚠️ {msg}")
            elif msg == '续费成功':
                logging.info(f"✅ 续费状态：{msg}")
                send_telegram_message(f"✅ 续费成功！")
            else:
                logging.error(f"❌ 续费失败，消息：{msg}")
                send_telegram_message(f"❌ 续费失败，服务器返回：{msg}")
        except ValueError:
            logging.warning("⚠️ 返回内容不是 JSON，原始响应如下：")
            logging.warning(response.text)
            send_telegram_message(f"⚠️ 无法解析续费响应：\n{response.text}")

    except Exception as e:
        logging.exception("❌ 续费请求失败：")
        send_telegram_message(f"❌ 续费失败：{str(e)}")


if __name__ == "__main__":
    session = login_session()
    if session:
        renew_server(session)
