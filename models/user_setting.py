from peewee import *

db = SqliteDatabase('bot.db')


class UserSetting(Model):
    user_id = IntegerField()
    cfg_scale = FloatField()
    sampler = TextField
    height = IntegerField()
    width = IntegerField()
    seed = IntegerField()
    messages = IntegerField()
    last_message = IntegerField()
    steps = IntegerField()
    user_name = TextField()

    class Meta:
        database = db
