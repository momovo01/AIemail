import email
import imaplib
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, parseaddr
from dataclasses import dataclass, field

import config


@dataclass
class Email:
    uid: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    date: str


def _decode_header_value(value: str) -> str:
    """解码邮件头中的编码字符串（如 =?UTF-8?B?...?=）"""
    if not value:
        return ""
    parts = decode_header(value)
    result = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += str(part)
    return result


def _parse_email_body(msg: email.message.Message) -> str:
    """提取邮件正文，优先纯文本，其次 HTML"""
    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or "utf-8"
                decoded = payload.decode(charset, errors="replace")
                if content_type == "text/plain" and not text_body:
                    text_body = decoded
                elif content_type == "text/html" and not html_body:
                    html_body = decoded
            except Exception:
                continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text_body = payload.decode(charset, errors="replace")
        except Exception:
            text_body = msg.get_payload()

    if text_body:
        return text_body.strip()
    if html_body:
        # 简单的 HTML 转纯文本，去除标签
        import re
        clean = re.sub(r"<style[^>]*>.*?</style>", "", html_body, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r"<[^>]+>", "", clean)
        clean = re.sub(r"\n\s*\n", "\n\n", clean)
        return clean.strip()
    return ""


def _get_imap_connection() -> imaplib.IMAP4_SSL:
    """建立 IMAP SSL 连接并登录"""
    conn = imaplib.IMAP4_SSL(config.IMAP_SERVER, config.IMAP_PORT)
    conn.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
    return conn


def fetch_unread_emails() -> list[Email]:
    """获取所有未读邮件，返回 Email 列表"""
    conn = _get_imap_connection()
    try:
        conn.select("INBOX")
        status, messages = conn.search(None, "UNSEEN")
        if status != "OK":
            return []

        email_ids = messages[0].split()
        emails: list[Email] = []

        for eid in email_ids:
            status, msg_data = conn.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw_email = response_part[1]
                    msg = email.message_from_bytes(raw_email)

                    sender_name, sender_email_addr = parseaddr(msg.get("From", ""))
                    sender_name = _decode_header_value(sender_name)
                    subject = _decode_header_value(msg.get("Subject", ""))
                    date = msg.get("Date", "")
                    body = _parse_email_body(msg)

                    emails.append(Email(
                        uid=eid.decode() if isinstance(eid, bytes) else eid,
                        sender_name=sender_name or sender_email_addr,
                        sender_email=sender_email_addr,
                        subject=subject,
                        body=body,
                        date=date,
                    ))
        return emails
    finally:
        conn.logout()


def mark_as_read(email_uid: str) -> None:
    """将指定邮件标记为已读"""
    conn = _get_imap_connection()
    try:
        conn.select("INBOX")
        # QQ 邮箱的 IMAP 使用 STORE +FLAGS (\Seen) 来标记已读
        if isinstance(email_uid, str):
            email_uid = email_uid.encode()
        conn.store(email_uid, "+FLAGS", "\\Seen")
    finally:
        conn.logout()


def send_email(to_address: str, to_name: str, subject: str, body: str) -> bool:
    """通过 SMTP 发送邮件，返回是否成功"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = formataddr(("AI 助手", config.EMAIL_ADDRESS))
    msg["To"] = formataddr((to_name, to_address))
    msg["Subject"] = subject

    try:
        conn = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        conn.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        conn.sendmail(config.EMAIL_ADDRESS, [to_address], msg.as_string())
        conn.quit()
        return True
    except Exception as e:
        print(f"发送邮件失败: {e}")
        return False
