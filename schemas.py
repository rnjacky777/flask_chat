# schemas.py
from pydantic import BaseModel, field_serializer
from datetime import datetime


class MessageSchema(BaseModel):
    timestamp: datetime
    user_id: int
    name: str
    message: str

    @field_serializer("timestamp")
    def serialize_timestamp(self, timestamp: datetime, _info):
        return timestamp.strftime('%Y-%m-%d %H:%M:%S')

    class Config:
        orm_mode = True
