"""
邮箱回复智能体 - 主入口

用法：
  python main.py check    # 单次检查：获取未读邮件，生成回复草稿
  python main.py run      # 持续轮询：定时检查未读邮件
  python main.py review   # 审核草稿：查看待发送的草稿，确认/拒绝发送
"""

import json
import logging
import os
import sys
import time
from datetime import datetime

# 解决 Windows 终端 GBK 编码 emoji 时报错的问题
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from email_client import fetch_unread_emails, mark_as_read, send_email
from ai_agent import analyze_email, generate_reply

DRAFTS_DIR = os.path.join(os.path.dirname(__file__), "drafts")
WHITELIST_FILE = os.path.join(os.path.dirname(__file__), "whitelist.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("email_agent.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def load_whitelist() -> list[dict]:
    """加载白名单发件人列表"""
    if not os.path.exists(WHITELIST_FILE):
        logger.warning("白名单文件不存在: %s", WHITELIST_FILE)
        return []
    with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("senders", [])


def save_draft(sender_email: str, sender_name: str, subject: str, reply_body: str, analysis: str) -> str:
    """保存回复草稿到本地，返回文件路径"""
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reply_{timestamp}_{sender_email.replace('@', '_at_')}.txt"
    filepath = os.path.join(DRAFTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"收件人: {sender_name} <{sender_email}>\n")
        f.write(f"主题: Re: {subject}\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        f.write("【邮件分析】\n")
        f.write(analysis + "\n\n")
        f.write("=" * 60 + "\n\n")
        f.write("【AI 生成回复】\n")
        f.write(reply_body)
    return filepath


def process_emails() -> int:
    """
    处理所有未读邮件：获取 → 白名单过滤 → AI 分析 → 生成回复 → 保存草稿
    返回处理的邮件数量
    """
    whitelist = load_whitelist()
    if not whitelist:
        logger.warning("白名单为空，不会处理任何邮件")
        return 0

    whitelist_emails = {entry["email"].lower() for entry in whitelist}
    whitelist_names = {entry["email"].lower(): entry.get("name", "") for entry in whitelist}

    logger.info("正在检查未读邮件...")
    emails = fetch_unread_emails()
    logger.info("共发现 %d 封未读邮件", len(emails))

    processed = 0
    for em in emails:
        sender_key = em.sender_email.lower()
        if sender_key not in whitelist_emails:
            logger.info("跳过非白名单发件人: %s <%s>", em.sender_name, em.sender_email)
            continue

        logger.info("=" * 50)
        logger.info("处理邮件 - 发件人: %s <%s>", em.sender_name, em.sender_email)
        logger.info("主题: %s", em.subject)

        # AI 分析
        logger.info("正在进行 AI 分析...")
        analysis = analyze_email(em.body, em.subject, em.sender_name)
        logger.info("分析结果:\n%s", analysis)

        # AI 生成回复
        logger.info("正在生成回复...")
        reply = generate_reply(em.body, em.subject, em.sender_name)

        # 保存草稿
        draft_path = save_draft(em.sender_email, em.sender_name, em.subject, reply, analysis)
        logger.info("回复草稿已保存: %s", draft_path)

        # 展示回复预览
        print("\n" + "=" * 60)
        print(f"📧 发件人: {em.sender_name} <{em.sender_email}>")
        print(f"📌 主题: {em.subject}")
        print("-" * 60)
        print("🤖 AI 生成的回复:")
        print(reply)
        print("=" * 60)

        # 交互式审核
        choice = input("\n是否发送此回复? (y=发送 / n=跳过 / q=退出): ").strip().lower()
        if choice == "y":
            reply_subject = f"Re: {em.subject}"
            success = send_email(em.sender_email, em.sender_name, reply_subject, reply)
            if success:
                logger.info("回复已发送给 %s", em.sender_email)
                mark_as_read(em.uid)
                logger.info("邮件已标记为已读")
            else:
                logger.error("发送失败，邮件保持未读状态")
        elif choice == "q":
            logger.info("用户选择退出")
            break
        else:
            logger.info("用户跳过此回复，草稿已保留")

        processed += 1
        print()

    return processed


def run_loop():
    """持续轮询模式"""
    interval = config.CHECK_INTERVAL
    logger.info("启动持续轮询模式，间隔 %d 秒", interval)
    logger.info("按 Ctrl+C 退出")
    try:
        while True:
            logger.info("--- 新一轮检查 ---")
            process_emails()
            logger.info("等待 %d 秒后进行下一次检查...", interval)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("收到退出信号，已停止")


def review_drafts():
    """审核草稿箱中的待发回复"""
    if not os.path.exists(DRAFTS_DIR):
        print("草稿箱为空")
        return

    drafts = sorted(os.listdir(DRAFTS_DIR))
    if not drafts:
        print("草稿箱为空")
        return

    for i, filename in enumerate(drafts):
        filepath = os.path.join(DRAFTS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"\n[{i + 1}/{len(drafts)}]")
        print(content)

        choice = input("操作: (s=发送 / d=删除草稿 / n=下一条 / q=退出): ").strip().lower()
        if choice == "s":
            # 从草稿中提取收件人信息
            lines = content.split("\n")
            to_line = lines[0]  # 收件人: name <email>
            subject_line = lines[1]  # 主题: Re: xxx

            import re
            to_match = re.search(r"<(.+?)>", to_line)
            to_name_match = re.search(r"收件人: (.+?) <", to_line)
            subject_match = re.search(r"主题: (.+)", subject_line)
            # 提取回复正文（【AI 生成回复】之后的内容）
            body_start = content.rfind("【AI 生成回复】\n")
            reply_body = content[body_start + len("【AI 生成回复】\n"):].strip()

            if to_match and subject_match and to_name_match:
                to_addr = to_match.group(1)
                to_name = to_name_match.group(1)
                subject = subject_match.group(1)
                success = send_email(to_addr, to_name, subject, reply_body)
                if success:
                    print(f"已发送给 {to_name} <{to_addr}>")
                    os.remove(filepath)
                else:
                    print("发送失败")
            else:
                print("无法解析草稿文件，跳过")

        elif choice == "d":
            os.remove(filepath)
            print("草稿已删除")
        elif choice == "q":
            break


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "check":
        count = process_emails()
        logger.info("处理完成，共处理 %d 封邮件", count)

    elif command == "run":
        run_loop()

    elif command == "review":
        review_drafts()

    else:
        print(f"未知命令: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
