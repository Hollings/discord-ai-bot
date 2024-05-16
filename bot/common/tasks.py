import asyncio
import base64
import io
import logging

import aiohttp
import discord
import requests
from celery import Celery
from common import celery_config
from discord import File, Message
from celery.signals import worker_process_init
from dotenv import dotenv_values
from cogs.image_gen.prompt import Prompt
from cogs.image_gen import txt2img
from PIL import Image

app = Celery('tasks')
app.config_from_object(celery_config)
config = dotenv_values('.env')
logger = logging.getLogger(__name__)

async def send_sleep_emoji(*, client, prompt_id):
    prompt= Prompt.get(Prompt.id == prompt_id)
    channel = await client.fetch_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    # send the sleepy guy emoji
    # if the sleepy guy emoji isnt already there, add it
    # remove thinking reaction
    if any(reaction.emoji == "🤔" for reaction in message.reactions):
        await message.remove_reaction("🤔", client.user)
    if not any(reaction.emoji == "😴" for reaction in message.reactions):
        await message.add_reaction("😴")

async def generate_gif_from_prompt(*, client: discord.Client, prompt_id):
    try:
        prompt = Prompt.get(Prompt.id == prompt_id)
    except Prompt.DoesNotExist:
        return
    if prompt.status != "pending":
        return

    channel = await client.fetch_channel(prompt.channel_id)
    children = Prompt.select().where(Prompt.parent_prompt_id == prompt.id).order_by(Prompt.id)

    if len(children) >100:
        children = children[:100]

    for child in children:
        child.status = "working"
        child.save()
    prompt.status = "working"
    prompt.save()
    try:
        message = await channel.fetch_message(prompt.message_id)
    except discord.NotFound:
        for child in children:
            child.status = "complete"
            child.save()
        prompt.status = "complete"
        prompt.save()
        return

    await message.add_reaction("🤔")

    message = await channel.fetch_message(prompt.message_id)
    prompts = [prompt, *children]

    #start the update process
    progress_bar = create_progress_bar(0.0, bar_length=max(len(prompt.text),10))
    progress_message = await channel.send("`"+prompt.text+"`\n`"+progress_bar + "`")
    update_task = asyncio.create_task(update_progress_bar_until_canceled(progress_message, prompt))
    image_list, _ = await txt2img.batch_text_to_image(prompts, parent_prompt_id=prompt.id)
    update_task.cancel()

    #end the process
    frames = []
    for index, image in enumerate(image_list):
        frames.append(image)

    frame_duration = 200
    filename = f'seed-{prompt.seed}-{prompt.id}.gif'
    saved_image = frames[0].save(filename, save_all=True, append_images=frames[1:], loop=0, duration=frame_duration, optimize=True)


    await message.remove_reaction("🤔", client.user)
    await message.add_reaction("✅")
    message = await message.channel.send(file=File(filename))

    try:
        await progress_message.delete()
    except discord.NotFound:
        pass

    # mark prompt as done
    prompt.status = "done"
    prompt.output_message_id = message.id
    prompt.save()
    for child in children:
        child.status = "done"
        child.save()

    return saved_image


async def generate_image_from_prompt(*, client: discord.Client, prompt_id):
    try:
        prompt = Prompt.get(Prompt.id == prompt_id)
    except Prompt.DoesNotExist:
        return
    if prompt.status != "pending" or prompt.status == "working":
        return
    logger.info("GENERATING PROMPT " + str(prompt_id))
    prompt.status = "working"
    prompt.save()
    channel = await client.fetch_channel(prompt.channel_id)
    try:
        message = await channel.fetch_message(prompt.message_id)
    except discord.NotFound:
        prompt.status = "failed"
        prompt.save()
        return
    await message.add_reaction("🤔")
    try:
        captioned_images, revised_prompt = await txt2img.text_to_image(prompt)
    except Exception as e:
        captioned_images = []
        await message.remove_reaction("🤔", client.user)
        await message.add_reaction("❌")
        prompt.status = "failed"
        prompt.save()
        await message.channel.send("Error: " + str(e))
        return
    tasks = []
    if len(captioned_images) == 0:
        await message.remove_reaction("🤔", client.user)
        await message.add_reaction("❌")
        prompt.status = "complete"
        prompt.save()
        return
    for i, captioned_image in enumerate(captioned_images):
        # Save PIL image to BytesIO object
        image_byte_arr = io.BytesIO()
        captioned_image.save(image_byte_arr, format='PNG')
        image_byte_arr.seek(0)

        # Send image to Discord channel
        discord_file = File(fp=image_byte_arr, filename='seed-'+str(prompt.seed + i)+'.png')

        if prompt.method == "dalle3":
            content = "> " + revised_prompt
        else:
            content = ""
        tasks.append(channel.send(file=discord_file, content=content))

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


def create_text_to_image_task(prompt: Prompt):
    logger.info("Creating task for prompt " + str(prompt.text) + " with method " + prompt.method)
    # check if the prompt has any children
    children = Prompt.select().where(Prompt.parent_prompt_id == prompt.id)
    if len(children) > 0:
        text_to_gif_task.delay(prompt.id)
    if prompt.method == 'stable-diffusion':
        text_to_image_task_local.delay(prompt.id)
    elif prompt.method == 'dalle3':
        text_to_image_task_api.delay(prompt.id)
    else:
        print("Invalid method")

@app.task(bind=True, name='text_to_image_task_local', queue='local', max_retries=None, default_retry_delay=600)
def text_to_image_task_local(self, prompt_id):
    logger.info("Running task for prompt " + str(prompt_id))
    try:
        # check http://localhost:7860/internal/ping for a response
        response = requests.get(f"{config['GRADIO_API_BASE_URL']}internal/ping")
        if response.status_code != 200:

            raise Exception("Local server not running")
        asyncio.run(run_method_with_bot(generate_image_from_prompt, prompt_id=prompt_id))
    except Exception as e:
        asyncio.run(run_method_with_bot(send_sleep_emoji, prompt_id=prompt_id))
        print("Retrying task, attempt number: %s", self.request.retries)
        self.retry(exc=e)

@app.task(name='text_to_image_task_api', queue='api')
def text_to_image_task_api(prompt_id):
    print("AAAAA")
    try:
        asyncio.run(
            run_method_with_bot(generate_image_from_prompt, prompt_id=prompt_id))
    except Exception as e:
        print("Error running gif task: " + str(e))
        return



@app.task(name='text_to_gif_task', queue='local')
def text_to_gif_task(prompt_id):
    print("AAAAA")
    try:
        asyncio.run(
            run_method_with_bot(generate_gif_from_prompt, prompt_id=prompt_id))
    except Exception as e:
        print("Error running gif task: " + str(e))
        return


@app.task(name='queue_all_pending_prompts_task')
def queue_all_pending_prompts_task():
    # get all prompts that are PENDING
    try:
        prompts = Prompt.select().where(
            ((Prompt.status == "pending") | (Prompt.status == "working")) &
            Prompt.parent_prompt_id.is_null(True)
        )
    except Exception as e:
        print("Error getting prompts: " + str(e))
        return
    logger.info("Queueing " + str(len(prompts)) + " prompts")
    for prompt in prompts:
        print("Queueing prompt " + str(prompt.text))
        create_text_to_image_task(prompt)



@worker_process_init.connect
def on_worker_init(**_):
    print("Worker process initialized, queueing all pending prompts")
    # queue_all_pending_prompts_task()



@app.task(queue='local')
def clear_queue():
    with app.connection_or_acquire() as conn:
        app.control.discard_all(connection=conn)


def create_progress_bar(percentage, bar_length=10, filled_char='█', empty_char=' '):
    filled_length = int(round(bar_length * percentage))
    empty_length = bar_length - filled_length
    percentage_str = f"{percentage*100:.0f}%"
    if len(percentage_str) < 3:
        percentage_str = empty_char + percentage_str
    bar = filled_char * filled_length + " " + percentage_str + empty_char * empty_length
    return f"|{bar}|"

async def update_progress_bar_until_canceled(message, prompt):

    async def fetch(session, url):
        async with session.get(url) as response:
            return await response.json()

    started = False
    async with aiohttp.ClientSession() as session:
        for i in range(0, 200):
            await asyncio.sleep(2)
            response = await fetch(session, config['GRADIO_API_BASE_URL'] + 'sdapi/v1/progress')

            # edit message with progress bar
            if response['progress'] != 0.0:
                started = True
            if response['progress'] == 0.0 and started:
                # delete the message
                await message.delete()
                return
            if response['progress'] > 0.0:
                progress_bar = create_progress_bar(response['progress'], bar_length=max(len(prompt.text),10))
                progress_message = f"""`{prompt.text}`
`{progress_bar}`"""
                await message.edit(content=progress_message)

