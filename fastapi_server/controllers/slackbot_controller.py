import logging
import inject

from fastapi import APIRouter, Request
from fastapi_server.slack import KISSlackBot


router = APIRouter(
    prefix="/v1/slackbot",
    tags=["Slackbot"],
)

slack_bot = inject.instance(KISSlackBot)


logger = logging.getLogger("api_logger")


@router.post("/send_message")
async def prophet(request: Request, input_text: str, channel_id: str):
    slack_bot.post_message(
        channel_id=channel_id,
        text=input_text,
    )
    logger.inform(
        input_text,
        extra={"endpoint_name": request.url.path}
    )

    return True
