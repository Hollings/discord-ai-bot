import json
import time

import discord
from dotenv import dotenv_values
from peewee import *

from image_editor import generate_txt_to_img, generate_img_to_txt, ImageData
from models.prompt import Prompt

db = SqliteDatabase('bot.db')

# load env variables
config = dotenv_values('.env')


def get_oldest_queued_prompt() -> Prompt:
    return Prompt.select().where(Prompt.queued == True).order_by(Prompt.id).first()


async def dequeue_prompt(prompt: Prompt, message):
    prompt.queued = False
    prompt.output_message_id = message.id
    channel = client.get_channel(prompt.channel_id)
    input_message = await channel.fetch_message(prompt.message_id)
    await input_message.add_reaction("✅")
    await input_message.remove_reaction("😶", client.user)
    await input_message.remove_reaction("😴", client.user)
    await input_message.remove_reaction("🤔", client.user)
    prompt.save()


async def send_image_to_discord(image_data: ImageData, prompt):
    channel = client.get_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    new_message = await message.channel.send(file=image_data.encode_to_discord_file())
    return new_message


async def send_text_to_discord(text_list, prompt):
    channel = client.get_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    new_message = await message.channel.send("\n___\n".join(text_list))
    return new_message


async def generate_queued_prompts():
    prompt = get_oldest_queued_prompt()
    while prompt:
        await do_prompt(prompt)
        prompt = get_oldest_queued_prompt()


async def do_prompt(prompt: Prompt):
    image_paths = json.loads(prompt.image_paths)
    output_message = None
    channel = client.get_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    await message.remove_reaction("😶", client.user)
    await message.add_reaction("🤔")
    if not image_paths:
        for i in range(prompt.quantity):
            image_data_list = generate_txt_to_img(prompt, 1)
            for image_data in image_data_list:
                image_data.upscale()
                image_data.add_caption_to_image(prompt.prompt, f"Seed: {prompt.seed}")
                # sending one image at a time, but we'll just save any one of the messages to log to the prompt db
                output_message = await send_image_to_discord(image_data, prompt)
            prompt.seed += 1
    else:
        images_description_list = [generate_img_to_txt(ImageData(image)) for image in image_paths]
        output_message = await send_text_to_discord(images_description_list, prompt)

    await dequeue_prompt(prompt, output_message)


class Client(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)
        client.loop.create_task(client.check_and_generate())

    async def check_and_generate(self):
        while (True):
            await generate_queued_prompts()
            time.sleep(1)


client = Client()
client.run(config['DISCORD_TOKEN'])
