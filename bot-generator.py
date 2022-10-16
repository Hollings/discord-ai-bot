import asyncio
import json
import logging
import time

import discord
import requests
from dotenv import dotenv_values
from peewee import *

from image_editor import generate_txt_to_img, generate_img_to_txt, ImageData
from models.global_config import GlobalConfig
from models.prompt import Prompt

db = SqliteDatabase('bot.db')

# load env variables
config = dotenv_values('.env')


def get_oldest_queued_prompt() -> Prompt:
    return Prompt.select().where(Prompt.status == "pending").order_by(Prompt.id).first()


def dequeue_prompt(prompt: Prompt, out_message=None):
    prompt.status = "complete"
    # prompt.output_message_id = out_message.id
    prompt.save()


def do_prompt(prompt: Prompt, message):
    print("======")
    image_paths = json.loads(prompt.image_paths)
    output_message = None
    prompts = json.loads(prompt.prompts)
    print("Generating prompt: " + prompts[0])
    files = []
    images_description_list = []
    if not image_paths:
        image_data_list = generate_txt_to_img(prompt)
        for i, image_data in enumerate(image_data_list):
            image_data.upscale()
            if prompt.apply_caption:
                try:
                    image_data.add_caption_to_image(prompts[i], f"Seed: {prompt.seed}")
                except:
                    pass
            files.append(image_data.encode_to_discord_file())
            prompt.seed += 1
    else:
        images_description_list = [generate_img_to_txt(ImageData(image), prompts[0]) for image in image_paths]

    return files, images_description_list


class Client(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)
        client.loop.create_task(client.check_and_generate(), name="check_and_generate")

    async def check_and_generate(self):

        global_config = GlobalConfig.get(GlobalConfig.setting == "generation_disabled")
        while global_config.value is not None:
            global_config = GlobalConfig.get(GlobalConfig.setting == "generation_disabled")
            await asyncio.sleep(2)

        seen = []
        prompt = get_oldest_queued_prompt()
        if prompt and prompt not in seen:
            seen.append(prompt)
            print("getting prompt")
            channel = client.get_channel(prompt.channel_id)
            # debug_channel = client.get_channel(config['DEBUG_CHANNEL_ID'])
            message = await channel.fetch_message(prompt.message_id)

            await message.add_reaction("🤔")

            files, descriptions = do_prompt(prompt, message)

            if files:
                # Send each file in its own message instead of a single message with multiple files
                # To make it easier for people to reply/react to a single one
                input_coroutines = [channel.send(file=file) for file in files]
                print("sending files for prompt " + prompt.prompts)
                res = await asyncio.gather(*input_coroutines, return_exceptions=False)
                print("sent files")

            for description in descriptions:
                try:
                    output_message = await asyncio.wait_for(channel.send(description, reference=message), timeout=60.0)
                except:
                    pass
            dequeue_prompt(prompt)
            await message.clear_reactions()
            await message.add_reaction("✅")
            print("finished prompt")

        running_tasks = [task for task in asyncio.all_tasks() if not task.done()]
        # group tasks by name
        task_names = {}
        for task in running_tasks:
            task_coro_name = task.get_coro().__name__
            if task_coro_name not in task_names:
                task_names[task_coro_name] = []
            task_names[task_coro_name].append(task)

        if "check_and_generate" in task_names and len(task_names["check_and_generate"]) > 1:
            print("Too many tasks running, cancelling")
            return
        await asyncio.sleep(2)
        client.loop.create_task(client.check_and_generate())

    async def on_error(self, event_method, *args, **kwargs):
        print("error")
        print(event_method)
        print(args)
        print(kwargs)

def wait_for_api():
    while True:
        try:
            requests.get("http://localhost:7860/")
            break
        except:
            print("Waiting for Web UI to start...")
            time.sleep(5)


wait_for_api()
logging.basicConfig(level=logging.ERROR)
client = Client()
client.run(config['DISCORD_TOKEN'])

