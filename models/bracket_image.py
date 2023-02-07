from peewee import *

db = SqliteDatabase('bot.db')


class BracketImage(Model):
    image_url = TextField()  # url of the image
    image_data = TextField(null=True)  # b64 encoded image
    post_id = IntegerField()  # link to the good-bot-posts post
    name = TextField(null=True)  # name of the image
    bracket_id = IntegerField(null=True)  # id of the bracket

    class Meta:
        database = db
