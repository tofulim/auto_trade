import os
import dotenv
import requests


dotenv.load_dotenv(f"./config/prod.env")


def update_kis_key():
    url = f"http://{os.getenv("FASTAPI_SERVER_HOST")}:{os.getenv("FASTAPI_SERVER_PORT")}/v1/trader/update_token"
    response = requests.get(
        url=url,
    )

    request_status = response.status_code
    response_answer = response

    print()
