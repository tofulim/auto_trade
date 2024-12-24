from pydantic import BaseModel


class SlackBase(BaseModel):
    input_text: str
    channel_id: str
