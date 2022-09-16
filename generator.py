import asyncio
import json
import os
import time
from random import randint
import re
import discord

from PIL import Image
import requests

def generate_gradio_api(prompt_data):
    batch_size = 1
    sampler = "Euler a"
    cfg_scale = 7
    height = 512
    width = 512
    start_time = time.time()
    model='stable-diffusion-v1'
    data = {"fn_index": 3,
            "data": [prompt_data['prompt'], prompt_data['negative_prompt'], "None", prompt_data['steps'], sampler, False, False, prompt_data['quantity'], batch_size, cfg_scale, prompt_data['seed'],
                     -1, 0, 0, 0, height, width, "None", None, False, "Seed", "", "Steps", "", [], "", ""],
            "session_hash": "aaa"}

    # todo dont hardcode this
    folder = f'Z:\\SD_outputs\\gradio'

    # delete all pngs in the folder if the folder exists
    if os.path.exists(folder):
        for file in os.listdir(folder):
            os.remove(folder + "\\" + file)

    r = requests.post("http://localhost:7860/api/predict/", json=data)

    with open(folder + '\\prompt.txt', mode="w") as prompt_file:
        prompt_file.write(prompt_data['prompt'])
    if prompt_data['caption']:
        add_caption_to_all_images_in_folder(folder, model, time.time() - start_time, prompt_data['quantity'])
    return folder


def add_caption_to_image(file, caption, model="", time=0, n=1):
    # Open the file with PIL
    image = Image.open(file)
    # expand the image with a white border
    margin_top = 128
    margin_bottom = 32
    margin_left = 32
    margin_right = 32

    x1, y1, x2, y2 = -margin_left, -margin_top, 512 + margin_right, 512 + margin_bottom  # cropping coordinates
    cropped_image = Image.new('RGB', (x2 - x1, y2 - y1), (255, 255, 255))
    cropped_image.paste(image, (-x1, -y1))

    # put text on the image
    from PIL import ImageFont
    from PIL import ImageDraw
    draw = ImageDraw.Draw(cropped_image)
    # center the text
    # Wrap the text so it fits in the image
    from textwrap import wrap
    lines = wrap(caption, width=37)
    # Draw the text
    y_text = 16

    if len(lines) > 5:
        lines = wrap(caption, width=70)
        font = ImageFont.truetype("arial.ttf", 18)
    elif len(lines) > 3:
        lines = wrap(caption, width=42)
        font = ImageFont.truetype("arial.ttf", 24)
    else:
        font = ImageFont.truetype("arial.ttf", 30)

    for line in lines:
        width, height = font.getsize(line)
        draw.text(((x2 - x1 - width) / 2, y_text), line, font=font, fill=(0, 0, 0))
        y_text += height

    # small font in the bottom corner

    font = ImageFont.truetype("arial.ttf", 12)
    seed = file.split("\\")[-1].split("-")[1]
    draw.text((12, 512 + margin_bottom + margin_top - 16), f'Seed {seed}        {model}', font=font, fill=(160, 160, 160))
    draw.text((512 + margin_left + margin_right - 24, 512 + margin_bottom + margin_top - 16), f'{time}s', font=font, fill=(160, 160, 160))

    cropped_image.paste(image, (-x1, -y1))

    cropped_image.save(file)
    cropped_image.close()

def add_caption_to_all_images_in_folder(folder = "", model="", time=0, n=1):
    prompt = open(folder + '\\prompt.txt', mode="r").read()
    for file in os.listdir(folder):
        if file.endswith(".png"):
            add_caption_to_image(folder + "\\" + file, prompt, model, time, n)

async def generate_from_queue(seen):
    # open prompt_queue.json
    with open('prompt_queue.json', 'r') as prompt_queue_file:
        prompt_queue = json.load(prompt_queue_file)
    # get the first element with None output_message_id
    for prompt in prompt_queue:
        if prompt['output_message_id'] is None and prompt['message_id'] not in seen:
            seen.add(prompt['message_id'])
            # get the discord message from "message_id"
            channel = client.get_channel(prompt['channel_id'])
            message = await channel.fetch_message(prompt['message_id'])

            await message.remove_reaction("😶", client.user)
            await message.add_reaction("🤔")

            # generate the image
            if prompt['image_path'] is None:
                try:
                    folder = generate_gradio_api(prompt)
                except Exception as e:
                    await message.add_reaction("💀")
                    print(str(e))
                    return seen

            # todo img2img

            # upload the images to discord
            files = [discord.File(folder + "\\" + f) for f in os.listdir(folder) if f.endswith(".png")]
            new_message = await message.channel.send(files=files)
            await new_message.remove_reaction("🤔", client.user)

            # update prompt_queue.json
            with open('prompt_queue.json', "r") as prompt_queue_file:
                new_prompt_queue = json.load(prompt_queue_file)

            new_prompt_queue[new_prompt_queue.index(prompt)]['output_message_id'] = new_message.id

            with open('prompt_queue.json', 'w') as prompt_queue_file:
                prompt_queue_file.write(json.dumps(new_prompt_queue))
            await message.remove_reaction("🤔", client.user)
            await asyncio.sleep(2)
            time.sleep(2)
            return seen
    await asyncio.sleep(2)
    time.sleep(2)
    return seen


with open('config/conf.json') as config_file:
    data = json.load(config_file)


class Client(discord.Client):
    seen = set()
    generating = False
    async def on_ready(self):
        print('Logged on as', self.user)
        client.loop.create_task(client.check_and_generate())

    async def check_and_generate(self):
        while(True):
            if not self.generating:
                self.generating = True
                self.seen = await generate_from_queue(self.seen)
                self.generating = False
            await asyncio.sleep(2)



client = Client()
client.run(data['token'])



