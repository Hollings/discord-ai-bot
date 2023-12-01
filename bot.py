import base64
import json
import logging
import os
import random
import subprocess
from random import randint

import discord
import requests
from dotenv import dotenv_values
from peewee import *
import psutil
from image_editor import ImageData
from models.channel_config import ChannelConfig
from models.global_config import GlobalConfig
from models.prompt import Prompt
from models.user_setting import UserSetting
from text_vestibule import respond_gpt

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.message_content = True
# load env variables
config = dotenv_values('.env')
config["SYSTEM_PROMPT"] = config.get("SYSTEM_PROMPT", "")


class Client(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config


client = Client(intents=intents, config=config)

db = SqliteDatabase('bot.db')

webui_process = None


# # Adjust TTS properties (Optional)
# tts_engine = pyttsx3.init()
#
# tts_engine.setProperty('rate', 300)  # Speed of speech
# tts_engine.setProperty('volume', 1.0)  # Volume (0.0 to 1.0)

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

    # bracket stuff
    if message.content == '!tournament':
        await message.channel.send('https://challonge.com/bestbotpostsrealbracket2')

    if message.content == '!bracket':
        await message.channel.send('https://challonge.com/bestbotpostsrealbracket2.svg')

    if message.content == '!goodpost':
        # post a random line from good-bot-posts.txt
        with open("good-bot-posts.txt", "r") as f:
            lines = f.readlines()
            await message.channel.send(random.choice(lines))
        return

    if message.content == "!system":
        # print system info
        await message.channel.send("Current System Prompt: ```" + config.get("SYSTEM_PROMPT", "(none)") + "```")
        return

    if message.content.startswith("!system "):
        system_prompt = message.content.replace("!system", "").strip()
        if system_prompt == "reset":
            system_prompt = ""
        config["SYSTEM_PROMPT"] = system_prompt
        await message.channel.send("Current System Prompt: ```" + config.get("SYSTEM_PROMPT", "(none)") + "```")
        return



    if message.channel.id == int(config["TEXT_AI_CHANNEL_ID"]):
        await respond_gpt(message, client)
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
            # I dont think this work

            # if " " in message.content:
            #     global_config.value = message.content.split(" ")[1]
            # else:
            #     global_config.value = "😴"
            # global_config.save()
            # global webui_process
            # webui_process.terminate()

            # Find the process with the name "webui.bat"
            for proc in psutil.Process.children():
                print(proc.name())
                if proc.name() == "webui.bat":
                    print("killing webui")
                    proc.kill()
                    break

            await client.change_presence(activity=discord.Game(name="Sleeping"), status=discord.Status.idle)
            return

        if message.content.startswith("!on"):
            await client.change_presence(activity=discord.Game(name="Stable Diffusion"),
                                         status=discord.Status.online)

            subprocess.Popen("webui.bat", cwd=config['WEB_UI_DIR'], shell=True)
            return

    # ignore messages from channels not in channelconfig or disabled
    if not ChannelConfig.select().where(ChannelConfig.channel_id == message.channel.id, ChannelConfig.enabled).exists():
        return

    # # send help message
    if message.content == "!help":
        help_message = config['HELP_MESSAGE']
        await message.channel.send(help_message)
        return

    try:
        message_list = split_sentence(message.content)
    except:
        message_list = [message.content]
    if len(message_list) > 1:
        seed = randint(0, 1000)
    else:
        seed = -1
    for message_content in message_list:
        await create_prompt_from_message(global_config, message, message_content, seed=seed)


def split_sentence(input_string):
    start_index = input_string.index("<") + 1
    end_index = input_string.index(">")
    options_string = input_string[start_index:end_index]
    options_list = options_string.split(",")
    sentence = input_string.replace(options_string, "")
    return [sentence.replace("<>", option.strip()) for option in options_list]


async def create_prompt_from_message(global_config, message, message_content="", seed=-1):
    prompt = Prompt(prompts=message_content, channel_id=message.channel.id, message_id=message.id, seed=seed)
    if len(message.attachments) >= 1:
        if not config['OPENAI_API_KEY']:
            # CLIP/GPT3 support is not enabled, so we can't do anything with uploaded images
            return None
        files = await download_attachments_from_message(message)
        prompt.image_paths = json.dumps([file.data for file in files])
        print("ADDING IMAGE PROMPT")
    elif not message_content.startswith("!"):
        return None
    if len(message.attachments) >= 1:
        if not config['OPENAI_API_KEY']:
            # CLIP/GPT3 support is not enabled, so we can't do anything with uploaded images
            return None
        files = await download_attachments_from_message(message)
        prompt.image_paths = json.dumps([file.data for file in files])
        print("ADDING IMAGE PROMPT")
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
    if reaction.message.guild.id == 631936246591127552:
        return

    # handle eyeball emoji reaction
    # if reaction.emoji == "👀":
    #     # download uploaded image
    #     message = await client.get_channel(reaction.message.channel.id).fetch_message(reaction.message.id)
    #     image_path = await message.attachments[0].save("input.jpg")
    #
    #     # run detect_and_add_eyes and send modified image
    #     if detect_and_add_eyes("input.jpg"):
    #         with open('result.png', 'rb') as result_image:
    #             await reaction.message.channel.send(file=discord.File(result_image, 'result.png'))

    # handle starboard channel reaction
    elif config.get('STARBOARD_CHANNEL_ID') and reaction.message.channel.id not in [1071835365729648690,
                                                                                    1022951067593494589]:
        # check that reaction is added by user on bot message with no other reactions
        if len(reaction.message.reactions) == 1 and (
                reaction.message.author == client.user or reaction.message.author.id == 1092594207878824068) and reaction.count == 1:
            link = reaction.message.attachments[
                0].url if reaction.message.attachments else f"> **{reaction.message.author.name}**: {reaction.message.content}"
            channel = client.get_channel(int(config['STARBOARD_CHANNEL_ID']))
            if channel.guild == reaction.message.guild:
                await channel.send(f"{reaction.message.jump_url}\n{link}")
            # add the image link to good-bot-posts.txt
            with open("good-bot-posts.txt", "a") as f:
                f.write(f"{link}\n")


async def download_attachments_from_message(message: discord.Message) -> list[ImageData]:
    return [ImageData(f"data:image/png;base64,{str(base64.b64encode(await attachment.read()).decode('utf-8'))}") for
            attachment in message.attachments if
            attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]


init_db(reset=False)

print("Starting the web UI...")
# webui_process = subprocess.Popen("webui-user.bat", cwd=config['WEB_UI_DIR'], shell=True)
print("Starting the generator script...")
subprocess.Popen(["./venv/Scripts/python", "bot-generator.py"])
print("Starting the Discord bot...")
discord.utils.setup_logging(level=logging.ERROR)
client.run(config['DISCORD_TOKEN'], log_level=logging.ERROR)
