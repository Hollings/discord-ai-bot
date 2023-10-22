import asyncio
import io

import discord
from celery import Celery
from discord import Message, File
from cogs.stable_diffusion.prompt import Prompt, PromptStatus
from cogs.stable_diffusion.txt2img import text_to_image
from common import celery_config
import time
from celery.signals import worker_process_init
from dotenv import dotenv_values

from main import initialize_bot

app = Celery('tasks')
app.config_from_object(celery_config)
config = dotenv_values('.env')


async def generate_image_from_prompt(*, client: discord.Client, prompt_id):
    prompt = Prompt.get(Prompt.id == prompt_id)
    prompt.status = "working"
    prompt.save()
    channel = await client.fetch_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    await message.add_reaction("🤔")

    captioned_images = text_to_image(prompt)
    tasks = []
    for captioned_image in captioned_images:
        # Save PIL image to BytesIO object
        image_byte_arr = io.BytesIO()
        captioned_image.save(image_byte_arr, format='PNG')
        image_byte_arr.seek(0)

        # Send image to Discord channel
        discord_file = File(fp=image_byte_arr, filename='image.png')
        tasks.append(channel.send(file=discord_file))

    await asyncio.gather(*tasks,
                         message.remove_reaction("🤔", client.user),
                         message.remove_reaction("🙄", client.user),
                         message.add_reaction("✅")
                         )
    prompt.status = "complete"
    prompt.save()


async def run_method_with_bot(the_method, **kwargs):
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.reactions = True
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        await the_method(client=client, **kwargs)
        await client.close()

    await client.login(config["DISCORD_TOKEN"])
    await client.connect()


@app.task(name='text_to_image_task')
def text_to_image_task(prompt_id):
    print("AAAAA")
    asyncio.run(
        run_method_with_bot(generate_image_from_prompt, prompt_id=prompt_id))

@app.task(name='queue_all_pending_prompts_task')
def queue_all_pending_prompts_task():
    # get all prompts that are PENDING
    prompts = Prompt.select().where(
        (Prompt.status == "pending") | (Prompt.status == "working")
    )
    for prompt in prompts:
        print(f"Queuing prompt {prompt.id}")
        text_to_image_task.delay(prompt.id)

@worker_process_init.connect
def on_worker_init(**_):
    pass
    queue_all_pending_prompts_task.delay()



