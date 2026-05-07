import logging
import os
from datetime import datetime, timedelta, timezone

import inject
from entity.slack_base import SlackAttachment, SlackBase
from fastapi import APIRouter, Request
from slack import KISSlackBot

router = APIRouter(prefix="/v1/slackbot", tags=["Slackbot"])

slack_bot = inject.instance(KISSlackBot)


logger = logging.getLogger("api_logger")


@router.post("/send_message")
async def send_message(request: Request, slack_base: SlackBase):
    slack_bot.post_message(channel_id=slack_base.channel_id, text=slack_base.input_text)
    logger.inform(slack_base.input_text, extra={"endpoint_name": request.url.path})

    return True


@router.post("/send_attachment")
async def send_attachment(request: Request, slack_attachment: SlackAttachment):
    slack_bot.post_attachment(
        channel_id=slack_attachment.channel_id,
        color=slack_attachment.color,
        pretext=slack_attachment.pretext,
        title=slack_attachment.title,
        text=slack_attachment.text,
        statistics=slack_attachment.field_dict,
    )
    logger.inform(slack_attachment.field_dict, extra={"endpoint_name": request.url.path})

    return True


@router.get("/check_rebalance_request")
async def check_rebalance_request(request: Request):
    """
    오늘 REBALANCE_REQUEST_CHANNEL 채널에 리밸런싱 요청 메시지가 있는지 확인한다.
    "리밸런싱", "rebalancing", "rebalance" 키워드가 포함된 메시지를 찾는다.

    Returns:
        dict: {"requested": bool}
    """
    channel_id = os.getenv("REBALANCE_REQUEST_CHANNEL")

    # 오늘 자정(KST) 이후의 메시지만 확인
    KST = timezone(timedelta(hours=9))
    today_midnight_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    oldest = str(today_midnight_kst.timestamp())

    messages = slack_bot.get_messages(channel_id=channel_id, oldest=oldest)

    rebalance_keywords = ["리밸런싱", "rebalancing", "rebalance"]
    requested = any(
        any(keyword in msg.get("text", "").lower() for keyword in rebalance_keywords) for msg in messages
    )

    logger.inform(f"Rebalance request check: {requested}", extra={"endpoint_name": request.url.path})

    return {"requested": requested}
