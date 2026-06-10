from openai import OpenAI

import config

client = OpenAI(
    api_key=config.DEEPSEEK_API_KEY,
    base_url=config.DEEPSEEK_BASE_URL,
)

SYSTEM_PROMPT = """你是一个友好亲切的邮件助手。你的任务是帮助用户阅读和回复邮件。

你的回复风格：
- 语气温暖、亲切，像朋友间的交流，但保持适度的礼貌
- 用词自然不生硬，可以适当使用"呀""哈""呢"等语气词让回复更有人情味
- 简洁明了，不要啰嗦，直击要点
- 根据对方邮件的语气和内容灵活调整回复风格

回复格式要求：
- 开头用恰当的问候语（如"你好"、"哈喽"等，根据情况灵活选择）
- 正文直接回复邮件内容
- 结尾用恰当的方式署名（如"祝好""回见"等）

注意事项：
- 不要透露这是 AI 生成的回复
- 如果邮件中问到你不确定的信息，诚实说明，不要编造
- 保持积极正面的态度"""


def analyze_email(email_body: str, subject: str, sender_name: str) -> dict:
    """分析邮件内容，返回意图摘要"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""请简要分析以下邮件，用 JSON 格式返回：
{{
    "intent": "邮件的主要意图（一句话概括）",
    "urgency": "紧急程度（低/中/高）",
    "key_points": ["关键信息点1", "关键信息点2"]
}}

发件人：{sender_name}
主题：{subject}
正文：
{email_body}"""},
        ],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content


def generate_reply(email_body: str, subject: str, sender_name: str) -> str:
    """根据邮件内容生成友好亲切的回复"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""请根据以下邮件内容，以友好亲切的风格写一封回信。

发件人：{sender_name}
主题：{subject}
正文：
{email_body}

请直接输出回复内容，不需要添加额外的说明。"""},
        ],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content
