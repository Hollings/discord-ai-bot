import asyncio
import base64
import io

import discord
import requests
from celery import Celery
from common import celery_config
from discord import File
from celery.signals import worker_process_init
from dotenv import dotenv_values
from cogs.image_gen.prompt import Prompt
from cogs.image_gen import txt2img
from PIL import Image

app = Celery('tasks')
app.config_from_object(celery_config)
config = dotenv_values('.env')

async def send_sleep_emoji(*, client, prompt_id):
    prompt= Prompt.get(Prompt.id == prompt_id)
    channel = await client.fetch_channel(prompt.channel_id)
    message = await channel.fetch_message(prompt.message_id)
    # send the sleepy guy emoji
    # if the sleepy guy emoji isnt already there, add it
    if not any(reaction.emoji == "🥱" for reaction in message.reactions):
        await message.add_reaction("🥱")

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

    image_list, _ = txt2img.batch_text_to_image(prompts, parent_prompt_id=prompt.id)
    frames = []
    for index, image in enumerate(image_list):
        frames.append(image)

    frame_duration = 200
    filename = f'seed-{prompt.seed}-{prompt.id}.gif'
    saved_image = frames[0].save(filename, save_all=True, append_images=frames[1:], loop=0, duration=frame_duration, optimize=False)


    await message.remove_reaction("🤔", client.user)
    await message.add_reaction("✅")
    message = await message.channel.send(file=File(filename))

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
    if prompt.status != "pending":
        return
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
        captioned_images, revised_prompt = txt2img.text_to_image(prompt)
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
    print("Creating task for prompt " + str(prompt.id) + " with method " + prompt.method)
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

@app.task(bind=True, name='text_to_image_task_local', queue='local', max_retries=None, default_retry_delay=30)
def text_to_image_task_local(self, prompt_id):
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
    asyncio.run(
        run_method_with_bot(generate_image_from_prompt, prompt_id=prompt_id))


@app.task(name='text_to_gif_task', queue='local')
def text_to_gif_task(prompt_id):
    print("AAAAA")
    asyncio.run(
        run_method_with_bot(generate_gif_from_prompt, prompt_id=prompt_id))


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
    print("Queueing " + str(len(prompts)) + " prompts")
    for prompt in prompts:
        create_text_to_image_task(prompt)



@worker_process_init.connect
def on_worker_init(**_):
    print("Worker process initialized, queueing all pending prompts")
    queue_all_pending_prompts_task.delay()



