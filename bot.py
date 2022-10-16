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
        return

    prompt = Prompt(prompts=[message.content], channel_id=message.channel.id, message_id=message.id)

    if len(message.attachments) >= 1:
        if not config['OPENAI_API_KEY']:
            # CLIP/GPT3 support is not enabled, so we can't do anything with uploaded images
            return
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


@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    # Add reacted images to the starboard channel
    if not config['STARBOARD_CHANNEL_ID']:
        return

    # we only care about reactions added by users on bot messages
    if (user == client.user) or len(reaction.message.reactions) > 1 or reaction.message.author != client.user:
        return

    # if there are already reactions on the message, ignore
    if sum([reaction.count for reaction in reaction.message.reactions]) > 1:
        return

    # get link of attachment
    link = reaction.message.attachments[0].url if len(reaction.message.attachments) >= 1 else ""
    # get channel by id
    channel = client.get_channel(int(config['STARBOARD_CHANNEL_ID']))
    if channel.guild != reaction.message.guild:
        return
    # send message with link
    await channel.send(reaction.message.jump_url + "\n" + link)


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
