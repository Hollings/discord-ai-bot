from peewee import *

db = SqliteDatabase('bot.db')


# really rough key/value table. Probably not the best way to do this
class GlobalConfig(Model):
    setting = TextField(null=True)
    value = TextField(null=True)

    class Meta:
        database = db
