import datetime
import json
from enum import Enum

import peewee
from peewee import *

db = PostgresqlDatabase('postgres', user='postgres', password='postgres',
                           host='postgres', port=5432)
class PromptStatus(Enum):
    PENDING = "pending"
    WORKING = "working"
    READY_TO_SEND = "ready_to_send"
    COMPLETE = "complete"
    FAILED = "failed"

class Prompt(peewee.Model):
    method = TextField(default="stable-diffusion")
    text = TextField(null=True)
    channel_id = TextField()
    message_id = TextField()
    user_id = TextField()
    created_at = DateTimeField(default=datetime.datetime.now)

    seed = IntegerField(default=-1)
    # parent_prompt = ForeignKeyField('self', null=True)
    output_message_id = TextField(null=True)
    model = TextField(default="stable-diffusion-v1")
    negative_prompt = TextField(default="")
    apply_caption = BooleanField(default=True)
    status = TextField(default="pending")
    steps = IntegerField(default=15)
    height = IntegerField(default=512)
    width = IntegerField(default=512)
    quantity = IntegerField(default=1)
    attachment_urls = TextField(TextField, default="[]")

    def to_json(self):
        return json.dumps({
            "method": self.method,
            "text": self.text,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "seed": self.seed,
            "output_message_id": self.output_message_id,
            "negative_prompt": self.negative_prompt,
            "apply_caption": self.apply_caption,
            "status": self.status,
            "steps": self.steps,
            "height": self.height,
            "width": self.width,
            "quantity": self.quantity,
            "attachment_urls": self.attachment_urls  # Assuming it's a JSON string
        })

    def __repr__(self):
        return self.text

    def __str__(self):
        return self.text

    class Meta:
        database = db