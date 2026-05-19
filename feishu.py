import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Feishu post messages have practical size limits; cap items per run.
_MAX_ITEMS_PER_MESSAGE = 12


def _post_payload(title: str, content_rows: list[list[dict]]) -> dict:
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content_rows,
                }
            }
        },
    }


def send_to_feishu_post(title: str, content_rows: list[list[dict]]) -> bool:
    webhook_url = os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        logger.error("FEISHU_WEBHOOK_URL not set in environment")
        return False

    try:
        response = requests.post(
            webhook_url,
            json=_post_payload(title, content_rows),
            timeout=30,
        )
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            body = {}
        code = body.get("code", body.get("StatusCode"))
        if code not in (0, None):
            logger.error("Feishu API error: %s", body)
            return False
        logger.info("Feishu post sent at %s", datetime.now().isoformat())
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send Feishu message: %s", e)
        return False


def _text_row(*parts: str) -> list[dict]:
    return [{"tag": "text", "text": part} for part in parts]


def _item_rows(index: int, title: str, summary: str, link: str) -> list[list[dict]]:
    rows: list[list[dict]] = [
        _text_row(f"\n{index}. 【标题】", title),
        _text_row(f"\n【摘要】", summary),
    ]
    if link:
        rows.append([{"tag": "a", "text": "阅读原文 →", "href": link}])
    else:
        rows.append(_text_row("\n【链接】", "（无链接）"))
    return rows


def send_feed_summary_to_feishu(feed_items: list) -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"📰 AI/RSS 日报 · {today}"

    if not feed_items:
        logger.info("No new feed items; sending empty-run notice")
        return send_to_feishu_post(
            title,
            [
                _text_row("今日没有在时间窗口内的新文章（或均已存在于 Reader）。"),
                _text_row("\n工作流已正常结束。"),
            ],
        )

    items = feed_items[:_MAX_ITEMS_PER_MESSAGE]
    rows: list[list[dict]] = [
        _text_row(f"共 {len(feed_items)} 篇新文章", "（仅展示前 " + str(len(items)) + " 篇）" if len(feed_items) > len(items) else ""),
    ]

    for i, item in enumerate(items, start=1):
        item_title = item.get("title", "无标题")
        summary = item.get("summary") or "（暂无摘要）"
        link = item.get("link", "")
        for row in _item_rows(i, item_title, summary, link):
            rows.append(row)

    if len(feed_items) > _MAX_ITEMS_PER_MESSAGE:
        rows.append(_text_row(f"\n… 另有 {len(feed_items) - _MAX_ITEMS_PER_MESSAGE} 篇已写入 Notion，请在 Reader 库查看。"))

    return send_to_feishu_post(title, rows)
