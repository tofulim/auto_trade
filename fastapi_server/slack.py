import logging
import requests
from io import BytesIO

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

    # 3.11 자로 slack side deprecated
    def deprecated_post_file(
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

    def post_file(
        self,
        file_path: str,
        filename: str,
        channel_id: str,
        thread_ts: str = None,
    ):
        # ID of the channel you want to send the message to
        file_stream = BytesIO()
        with open(file_path, "rb") as f:
            file_stream.write(f.read())

        file_stream.seek(0, 2)  # 파일 끝으로 이동하여 크기 확인
        length = file_stream.tell()
        file_stream.seek(0)  # 다시 처음으로 이동

        try:
            # 1. 파일 업로드할 url 받기
            result = self.client.files_getUploadURLExternal(
                filename=filename,
                length=length,
            )
            logger.info(result)

            upload_url_data = result
            upload_url = upload_url_data["upload_url"]
            file_id = upload_url_data["file_id"]
            # 2. 업로드 URL로 이미지 업로드
            requests.post(
                upload_url,
                files={'file': (filename, file_stream, "image/jpeg")}  # MIME 타입 설정 (JPG/PNG 등)
            )

            # 3. 업로드 완료 요청
            self.client.files_completeUploadExternal(
                files=[
                    {"id": file_id, "title": filename}
                ],
                channel_id=channel_id,
                thread_ts=thread_ts,
            )

            return result

        except SlackApiError as e:
            logger.error(f"Error posting message: {e}")


if __name__ == "__main__":
    slackbot = KISSlackBot(slack_bot_token="xoxb-...")
    # slackbot.post_message(
    #     channel_id="test",
    #     # thread_ts="1722946045.578359",
    #     text="on test",
    # )

    slackbot.post_file(
        file_path = "/Users/limdohoon/PycharmProjects/auto-trade/test.png",
        filename="test_file",
        channel_id="C08FRRB60Q6",
        # thread_ts=
    )
