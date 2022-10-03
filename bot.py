import base64
import json
import random
from random import randint

import discord
import requests
from dotenv import dotenv_values
from peewee import *

from image_editor import ImageData
from models.channel_config import ChannelConfig
from models.prompt import Prompt
from models.user_setting import UserSetting

client = discord.Client()
db = SqliteDatabase('bot.db')

# load env variables
config = dotenv_values('.env')


def init_db(migrate: bool = False):
    db.connect()
    if migrate:
        db.drop_tables([Prompt, UserSetting, ChannelConfig])
        db.create_tables([Prompt, UserSetting, ChannelConfig])

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


@client.event
async def on_message(message: discord.Message):
    # ignore messages from self
    if message.author == client.user:
        return

    # ignore messages from channels not in channelconfig
    if not ChannelConfig.select().where(ChannelConfig.channel_id == message.channel.id).exists():
        return

    # send help message
    if message.content == "!help":
        await message.channel.send(config["HELP_MESSAGE"])

    prompt = Prompt(prompt=message.content, channel_id=message.channel.id, message_id=message.id)

    if len(message.attachments) >= 1:
        files = await download_attachments_from_message(message)
        prompt.image_paths = json.dumps([file.data for file in files])
    elif not message.content.startswith("!"):
        return

    prompt.apply_modifiers()

    if prompt.seed == -1:
        prompt.seed = random.randint(0, 1000)
    prompt.save()
    await message.add_reaction("😶")
    try:
        requests.get("http://localhost:7860/")
    except:
        await message.remove_reaction("😶", client.user)
        await message.add_reaction("😴")


async def download_attachments_from_message(message: discord.Message) -> list[ImageData]:
    prompt_files = []
    for attachment in message.attachments:
        if attachment.filename.endswith(".png") or attachment.filename.endswith(".jpg"):
            # generate a random filename
            filename = f"images/{attachment.filename}_{randint(0, 1000000)}"
            # download file as bytes
            file_bytes = await attachment.read()
            image_data = ImageData("data:image/png;base64," + str(base64.b64encode(file_bytes).decode("utf-8")))
            prompt_files.append(image_data)
    return prompt_files


init_db(migrate=False)
client.run(config['DISCORD_TOKEN'])
