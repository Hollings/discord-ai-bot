from peewee import *

db = SqliteDatabase('bot.db')


class ChannelConfig(Model):
    channel_id = IntegerField()
    enabled = BooleanField(default=True)
    name = TextField(default="")

    class Meta:
        database = db
