import datetime
import json
from enum import Enum

import peewee
from peewee import *

db = PostgresqlDatabase('postgres', user='postgres', password='postgres',
                           host='postgres', port=5432)

class SystemPrompt(peewee.Model):

    content = TextField(null=True)
    active_on = DateTimeField(default=None, null=True)

    def set_active(self):
        # set all other system prompts to inactive
        SystemPrompt.update(active_on=None).where(SystemPrompt.active_on.is_null(False)).execute()
        # set this one to active
        self.active_on = datetime.datetime.now()
        self.save()

    class Meta:
        database = db