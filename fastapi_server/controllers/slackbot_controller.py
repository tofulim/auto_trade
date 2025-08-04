import logging

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
