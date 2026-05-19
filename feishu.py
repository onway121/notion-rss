import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_MAX_ITEMS_PER_MESSAGE = 12


def _is_flow_webhook(url: str) -> bool:
    """飞书流程自动化 Webhook，与群自定义机器人格式不同。"""
    return "/flow/" in url


def _send_text(webhook_url: str, text: str) -> bool:
    """群自定义机器人标准 text 消息（兼容性最好）。"""
    payload = {
        "msg_type": "text",
        "content": {"text": text},
    }
    return _post_webhook(webhook_url, payload)


def _send_post(webhook_url: str, title: str, body_lines: list[str]) -> bool:
    """富文本 post；部分客户端要求 zh_cn，部分要求 zh-CN，两个都带上。"""
    content_block = [
        [{"tag": "text", "text": line}] for line in body_lines if line.strip()
    ]
    post_body = {"title": title, "content": content_block}
    payload = {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": post_body,
                "zh-CN": post_body,
            }
        },
    }
    return _post_webhook(webhook_url, payload)


def _post_webhook(webhook_url: str, payload: dict) -> bool:
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            body = {}
        code = body.get("code", body.get("StatusCode"))
        if code not in (0, None):
            logger.error("Feishu API error: %s", body)
            return False
        logger.info("Feishu message sent at %s", datetime.now().isoformat())
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send Feishu message: %s", e)
        return False


def _format_item(index: int, title: str, summary: str, link: str) -> str:
    lines = [
        f"{index}. 【标题】{title}",
        f"【摘要】{summary}",
    ]
    if link:
        lines.append(f"【链接】{link}")
    else:
        lines.append("【链接】（无）")
    return "\n".join(lines)


def _build_message_text(feed_items: list) -> tuple[str, str]:
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"AI/RSS 日报 · {today}"

    if not feed_items:
        body = (
            "今日没有在时间窗口内的新文章（或均已存在于 Reader）。\n"
            "工作流已正常结束。"
        )
        return title, body

    items = feed_items[:_MAX_ITEMS_PER_MESSAGE]
    parts = [f"共 {len(feed_items)} 篇新文章"]
    if len(feed_items) > len(items):
        parts[0] += f"（仅展示前 {len(items)} 篇）"

    for i, item in enumerate(items, start=1):
        item_title = item.get("title", "无标题")
        summary = item.get("summary") or "（暂无摘要）"
        link = item.get("link", "")
        parts.append(_format_item(i, item_title, summary, link))

    if len(feed_items) > _MAX_ITEMS_PER_MESSAGE:
        extra = len(feed_items) - _MAX_ITEMS_PER_MESSAGE
        parts.append(f"… 另有 {extra} 篇已写入 Notion，请在 Reader 库查看。")

    return title, "\n\n".join(parts)


def send_feed_summary_to_feishu(feed_items: list) -> bool:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        logger.error("FEISHU_WEBHOOK_URL not set in environment")
        return False

    title, body = _build_message_text(feed_items)
    full_text = f"{title}\n\n{body}"

    # 流程 Webhook 或非 open.feishu.cn 机器人地址：只用纯文本
    if _is_flow_webhook(webhook_url):
        logger.info("Using text mode for Feishu flow webhook")
        return _send_text(webhook_url, full_text)

    # 群自定义机器人：优先 text（最稳），失败再试 post
    if _send_text(webhook_url, full_text):
        return True

    logger.warning("Text message failed, retrying with post format")
    return _send_post(webhook_url, title, body.split("\n\n"))
