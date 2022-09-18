import asyncio
import json
import os
import time

import discord
import requests
from wand.color import Color


def generate_gradio_api(prompt_data):
    batch_size = 1
    sampler = "Euler a"
    cfg_scale = 7
    height = 512
    width = 512
    start_time = time.time()
    model = 'stable-diffusion-v1'
    data = {"fn_index": 3,
            "data": [prompt_data['prompt'], prompt_data['negative_prompt'], "None", prompt_data['steps'], sampler,
                     False, False, prompt_data['quantity'], batch_size, cfg_scale, prompt_data['seed'],
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
    # put text on the image
    from wand.image import Image as wImage
    from wand.drawing import Drawing
    from wand.font import Font

    seed = file.split("-")[1]
    # expand the image with a white border
    margin_top = 128 if len(caption) > 50 else 64
    margin_bottom = 16
    margin_left = 16
    margin_right = 16

    with wImage(filename=file) as img:
        # expand the image by margins
        img.border(color='white', width=margin_left, height=margin_top)
        # crop the bottom margin
        img.crop(width=img.width, height=img.height - margin_top + margin_bottom, gravity='north')
        # add the caption to fit in the margin_top
        left, top, width, height = margin_left, 10, 512, margin_top - 10
        with Drawing() as context:
            context.fill_color = 'white'
            context.rectangle(left=left, top=top, width=width, height=height)
            font = Font('/System/Library/Fonts/MarkerFelt.ttc')
            context(img)
            img.caption(caption, left=left, top=top, width=width, height=height, font=font, gravity='center')

        # add the model, seed, and time to the bottom margin
        left, top, width, height = 15, img.height - 15, 512, 15
        with Drawing() as context:
            context.fill_color = 'white'
            context.rectangle(left=left, top=top, width=width, height=height)
            font = Font('/System/Library/Fonts/MarkerFelt.ttc', color=Color('#AAA'))
            context(img)
            img.caption(f'{model}    Seed {seed}    {time} seconds', left=left, top=top, width=width, height=height,
                        font=font, gravity='west')
        img.save(filename=file)


def add_caption_to_all_images_in_folder(folder="", model="", time=0, n=1):
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
        while (True):
            if not self.generating:
                self.generating = True
                self.seen = await generate_from_queue(self.seen)
                self.generating = False
            await asyncio.sleep(2)


#
# short_text = "This is a test."
# medium_text = "The quick brown fox jumps over the lazy dog. Hello"
# long_text = "The quick brown fox jumps over the lazy dog. This is a test. Lorem Ipsum. DeprecationWarning: getsize is deprecated and will be removed in Pillow 10 (2023-07-01). Use getbbox or getlength instead."
#
# add_caption_to_image("Z:\\SD_outputs\\gradio\\00001-55-Peering into the soul of a Minion. Unholy eldritch horror - award winning, DSLR, intricate details, masterpiece, nature photogra (2).png", long_text, "test", 0, 1)
# exit()
client = Client()
client.run(data['token'])
