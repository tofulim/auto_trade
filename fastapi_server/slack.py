import logging
from typing import Union

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


logger = logging.getLogger()


class KISSlackBot:
    def __init__(self, slack_bot_token: str):
        self.client = WebClient(token=slack_bot_token)

    def post_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str = None,
    ):
        # ID of the channel you want to send the message to
        try:
            # Call the chat.postMessage method using the WebClient
            result = self.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=text
            )
            logger.info(result)
            return result

        except SlackApiError as e:
            logger.error(f"Error posting message: {e}")

    def post_file(
        self,
        save_path: str,
        thread_ts: str = None,
        channel_id: str = None,
    ):
        # ID of the channel you want to send the message to
        try:
            # Call the chat.postMessage method using the WebClient
            result = self.client.files_upload_v2(
                channel=channel_id,
                thread_ts=thread_ts,
                file=save_path,
            )
            logger.info(result)
            return result

        except SlackApiError as e:
            logger.error(f"Error posting message: {e}")


if __name__ == "__main__":
    slackbot = KISSlackBot(slack_bot_token="xoxb-...")
    slackbot.post_message(
        channel_id="test",
        # thread_ts="1722946045.578359",
        text="on test",
    )
