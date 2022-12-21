import base64
import json
import os
import random
import subprocess
import time
from random import randint

import discord
import requests
from dotenv import dotenv_values
from peewee import *

from image_editor import ImageData
from models.channel_config import ChannelConfig
from models.global_config import GlobalConfig
from models.prompt import Prompt
from models.user_setting import UserSetting

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.message_content = True
client = discord.Client(intents=intents)

db = SqliteDatabase('bot.db')

# load env variables
config = dotenv_values('.env')


def init_db(reset: bool = False):
    db.connect()

    if reset:
        db.drop_tables([Prompt, UserSetting, ChannelConfig, GlobalConfig])

    db.create_tables([Prompt, UserSetting, ChannelConfig, GlobalConfig])

    GlobalConfig.get_or_create(setting="generation_disabled", defaults={"value": None})

@client.event
async def on_ready():
    print('bot.py logged in as {0.user}'.format(client))


@client.event
async def on_message(message: discord.Message):
    # ignore messages from self
    if message.author == client.user:
        return

    # admin can turn on and off generation and give an emoji for the bot to react to messages with
    global_config = GlobalConfig.get(GlobalConfig.setting == "generation_disabled")
    if message.author.id == int(config["ADMIN_USER_ID"]):
        if message.content == "!add":
            # create channelconfig for this channel
            ChannelConfig.get_or_create(channel_id=message.channel.id, defaults={"enabled": True})
            await message.add_reaction("✅")
            return
        if message.content == "!remove":
            # delete channelconfig for this channel
            ChannelConfig.delete().where(ChannelConfig.channel_id == message.channel.id).execute()
            await message.add_reaction("✅")
            return

        if message.content.startswith("!off"):
            if " " in message.content:
                global_config.value = message.content.split(" ")[1]
            else:
                global_config.value = "😴"
            global_config.save()
            await client.change_presence(activity=discord.Game(name="Sleeping"), status=discord.Status.idle)
            return

        if message.content.startswith("!on"):
            await client.change_presence(activity=discord.Game(name="Stable Diffusion"),
                                         status=discord.Status.online)
            global_config.value = None
            global_config.save()
            return

    # ignore messages from channels not in channelconfig or disabled
    if not ChannelConfig.select().where(ChannelConfig.channel_id == message.channel.id, ChannelConfig.enabled).exists():
        return

    # # send help message
    # if message.content == "!help":
    #     # get .bin filenames in models directory
    #     loaded_textual_inversions = [f for f in os.listdir(config['WEB_UI_DIR']+"/embeddings") if f.endswith(".bin")]
    #
    #     help_message = config['HELP_MESSAGE']
    #     if loaded_textual_inversions:
    #         help_message+="\n\n" + "Available Textual Inversions embeddings: " + ", ".join([f"`{x.replace('.bin','')}`" for x in loaded_textual_inversions])
    #
    #     await message.channel.send()
    #     return

    if not message.content.startswith("!"):
        return

    prompt = Prompt(prompts=message.content, channel_id=message.channel.id, message_id=message.id)

    # if len(message.attachments) >= 1:
    #     if not config['OPENAI_API_KEY']:
    #         # CLIP/GPT3 support is not enabled, so we can't do anything with uploaded images
    #         return
    #     files = await download_attachments_from_message(message)
    #     prompt.image_paths = json.dumps([file.data for file in files])
    # el

    prompt.apply_modifiers()
    if prompt.seed == -1:
        prompt.seed = random.randint(0, 1000)
    prompt.save()
    await message.add_reaction("😶")
    if global_config.value is not None:
        try:
            await message.add_reaction(global_config.value)
        except:
            await message.add_reaction("😴")
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
    if len(reaction.message.reactions) > 1 or reaction.message.author != client.user:
        return

    # if there are already reactions on the message, ignore
    if sum([reaction.count for reaction in reaction.message.reactions]) > 1:
        return

    # get link of attachment
    link = reaction.message.attachments[0].url if len(reaction.message.attachments) >= 1 else ""
    # Get the text of the message

    if not link:
        text = reaction.message.content
        # Get the name of the user who added the reaction
        user_name = reaction.message.author.name
        link = f"> **{user_name}**: {text}"

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


init_db(reset=False)
print("Starting the web UI...")
subprocess.Popen("webui.bat", cwd=config['WEB_UI_DIR'], shell=True)
print("Starting the generator script...")
subprocess.Popen(["./venv/Scripts/python", "bot-generator.py"])
print("Starting the Discord bot...")
client.run(config['DISCORD_TOKEN'])
