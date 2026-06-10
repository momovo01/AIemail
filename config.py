import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    if not value:
        raise ValueError(f"缺少必要的环境变量: {key}，请在 .env 文件中配置")
    return value


DEEPSEEK_API_KEY = _get_env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _get_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

EMAIL_ADDRESS = _get_env("EMAIL_ADDRESS")
EMAIL_PASSWORD = _get_env("EMAIL_PASSWORD")

IMAP_SERVER = _get_env("IMAP_SERVER", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

SMTP_SERVER = _get_env("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))
