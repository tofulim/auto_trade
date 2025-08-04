from pydantic import BaseModel


class SlackBase(BaseModel):
    input_text: str
    channel_id: str


class SlackAttachment(BaseModel):
    channel_id: str
    color: str
    pretext: str = None
    title: str = None
    text: str = None
    field_dict: dict = {}

    def to_dict(self):
        return {
            "channel_id": self.channel_id,
            "color": self.color,
            "pretext": self.pretext,
            "title": self.title,
            "text": self.text,
            "field_dict": self.field_dict,
        }
