import logging

import inject
from entity.slack_base import SlackBase
from fastapi import APIRouter, Request
from slack import KISSlackBot

router = APIRouter(prefix="/v1/slackbot", tags=["Slackbot"])

slack_bot = inject.instance(KISSlackBot)


logger = logging.getLogger("api_logger")


@router.post("/send_message")
async def prophet(request: Request, slack_base: SlackBase):
    slack_bot.post_message(channel_id=slack_base.channel_id, text=slack_base.input_text)
    logger.inform(slack_base.input_text, extra={"endpoint_name": request.url.path})

    return True
