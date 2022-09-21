import asyncio
import base64
import json
import os
import sqlite3
import time

import discord
import requests
from wand.color import Color


def generate_gradio_img2img(prompt_data):
    with open(prompt_data['image_path'], "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    data_encoded_string = "data:image/png;base64," + encoded_string.decode("utf-8")
    data = {"fn_index": 14,
            "data": [data_encoded_string],
            "session_hash": "aaa"}


def interrogate_image(file):
    # file to base64 data:image/png;base64,
    with open(file, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    data_encoded_string = "data:image/png;base64," + encoded_string.decode("utf-8")
    data = {"fn_index": 14,
            "data": [data_encoded_string],
            "session_hash": "aaa"}
    r = requests.post("http://localhost:7860/api/predict/", json=data)
    caption = r.json()['data'][0]
    # send a message to the channel with caption
    return caption


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
    try:
        with open(folder + '\\prompt.txt', mode="w") as prompt_file:
            prompt_file.write(prompt_data['prompt'])
        if prompt_data['caption']:
            add_caption_to_all_images_in_folder(folder, model, time.time() - start_time, prompt_data['quantity'])
    except Exception as e:
        print("error", str(e))

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
        left, top, width, height = margin_left, 5, 512, margin_top - 10
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
            img.caption(f'{model}        Seed {seed}        {round(time)} seconds', left=left, top=top, width=width,
                        height=height,
                        font=font, gravity='west')
        img.save(filename=file)


def add_caption_to_all_images_in_folder(folder="", model="", time=0, n=1):
    prompt = open(folder + '\\prompt.txt', mode="r").read()
    for file in os.listdir(folder):
        if file.endswith(".png"):
            add_caption_to_image(folder + "\\" + file, prompt, model, time, n)


async def generate_from_queue(seen):
    # open prompt_queue.json
    # with open('prompts.json', 'r') as prompt_queue_file:
    #     prompt_queue = json.load(prompt_queue_file)
    # get the first element with None output_message_id

    # Query sqlite for the oldest queued prompt
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute("SELECT * FROM prompts WHERE queued IS TRUE ORDER BY message_id ASC LIMIT 1")
    prompt = c.fetchone()

    if prompt is None:
        return seen

    # result to dict
    prompt = {
        "prompt": prompt[0],
        "quantity": prompt[1],
        "channel_id": prompt[2],
        "message_id": prompt[3],
        "seed": prompt[4],
        "image_path": prompt[5],
        "output_message_id": prompt[6],
        "model": prompt[7],
        "negative_prompt": prompt[8],
        "caption": prompt[9],
        "queued": prompt[10],
        "steps": prompt[11]
    }
    print(prompt)
    if prompt is None:
        return seen
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
                await message.remove_reaction("🤔", client.user)
                await message.add_reaction("💀")
                print(str(e))
                return seen
        else:
            caption = interrogate_image(prompt['image_path'])
            new_message = await message.channel.send(caption)
            await message.remove_reaction("🤔", client.user)
            await asyncio.sleep(2)

            # update the db row with the output_message_id and set queued to false
            c.execute("UPDATE prompts SET output_message_id = ?, queued = ? WHERE message_id = ?",
                      (new_message.id, False, prompt['message_id']))
            conn.commit()
            conn.close()
            return seen

        # todo img2img

        # upload the images to discord
        files = [discord.File(folder + "\\" + f) for f in os.listdir(folder) if f.endswith(".png")]
        new_message = await message.channel.send(files=files)
        await new_message.remove_reaction("🤔", client.user)

        # update the db row with the output_message_id and set queued to false
        c.execute("UPDATE prompts SET output_message_id = ?, queued = ? WHERE message_id = ?",
                  (new_message.id, False, prompt['message_id']))
        conn.commit()

        await message.remove_reaction("🤔", client.user)
        await asyncio.sleep(2)
        time.sleep(2)
        conn.close()
        return seen
    await asyncio.sleep(2)
    time.sleep(2)
    conn.close()
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


# interrogate_image("result.png")
# exit()
#
# short_text = "This is a test."
# medium_text = "The quick brown fox jumps over the lazy dog. Hello"
# long_text = "The quick brown fox jumps over the lazy dog. This is a test. Lorem Ipsum. DeprecationWarning: getsize is deprecated and will be removed in Pillow 10 (2023-07-01). Use getbbox or getlength instead."
#
# add_caption_to_image("Z:\\SD_outputs\\gradio\\00001-55-Peering into the soul of a Minion. Unholy eldritch horror - award winning, DSLR, intricate details, masterpiece, nature photogra (2).png", long_text, "test", 0, 1)
# exit()

client = Client()
client.run(data['token'])
