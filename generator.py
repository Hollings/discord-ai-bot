import asyncio
import base64
import json
import os
import random
import sqlite3
import subprocess
import time

import discord
import openai
import requests
from wand.color import Color

folder = f'Z:\\SD_outputs\\gradio'


def upscale(encoded_image, size=2):
    # print(encoded_image)
    data = {
        "fn_index": 20,
        "data": [
            encoded_image,
            0,
            0,
            0,
            size,
            "Lanczos",
            "None",
            1
        ],
        "session_hash": "abasbasb"
    }
    r = requests.post("http://localhost:7860/api/predict/", json=data)
    # print(r.json())
    encoded_image = r.json()['data'][0]
    # decode base64 image to file
    return encoded_image


def generate_gradio_img2img(prompt_data):
    with open(prompt_data['image_path'], "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    data_encoded_string = "data:image/png;base64," + encoded_string.decode("utf-8")
    data = {"fn_index": 14,
            "data": [data_encoded_string],
            "session_hash": "aaa"}


def interrogate_image(file, prompt):
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
    gpt_options = [
        "You are a news anchor who is reporting on this image. Please write a 5 sentence script for a breaking news story related to this image. You don't need to describe the image to the viewers:",
        "Please write your opinion about this image in 3 or more sentences. Do not restate the description:",
        "You are in love with this image. What do you have to say about it?",
        "You absolutely hate this image. What do you have to say about it?",
        "You are very bored with this image. What do you have to say about it? Be descriptive:",
        "You are very excited about this image. You've never seen anything like it before. What do you have to say about it?",
        "Please describe what you would add to this image to make it better. Then describe what you would remove from this image. Explain your reasoning:",
        "Please describe your favorite part and least favorite part of this image and describe why:",
        "Please write a newspaper headline and a short article about this image:",
        "Please write a 5 line poem about this image:",
        "Please write a 5 line thoughtful poem about this image:",
        "Please write a 5 line funny poem about this image:",
        "Please write two beautiful haikus about this image:",
        "Please write two high quality haikus about this image:",
        "Please write two haikus about this image:",
        "Describe why this image is significant to you. Explain your reasoning in 3 sentences:",
        "What event in your life does this picture remind you of?",
        "Please describe the historical and socioeconomic importance of this image.",
        "Please describe how this image smells. tastes, sounds, and feels to you:",
        "Pretend you are an auctioneer describing this image to a crowd of art buyers:",
        "Describe this image in 5 sentences as if you were a famous art critic:",
        "Describe this image in a foreign language:",
    ]
    response = ""
    for i in range(0, 5):
        if len(response) < 10:
            if not prompt:
                choice = f"""The following is a description of an image: '{caption}'
                
                {random.choice(gpt_options)}"""
            else:
                choice = f"""The following is a description of an image: '{caption}'
                
                {prompt}
                
                """

            response = openai.Completion.create(
                engine="text-davinci-001",
                prompt=choice,
                max_tokens=200,
                temperature=1.0,
                echo=False,
            )['choices'][0]['text']
            print(caption, choice, response)
    # chop the end of the response off to the period
    # response = response[:response.rfind('.') + 1]

    return f"{response}"

def generate_gradio_api(prompt_data):
    quantity = int(prompt_data['quantity'])
    batch_size = 1

    # This doesnt really give much speedup

    # if prompt_data['quantity'] % 2 == 0:
    #     batch_size = 2
    #     quantity = int(quantity / 2)

    sampler = "Euler a"
    cfg_scale = 7
    height = prompt_data['height']
    width = prompt_data['width']
    start_time = time.time()
    model = 'stable-diffusion-v1'
    data = {"fn_index": 3,
            "data": [prompt_data['prompt'], prompt_data['negative_prompt'], "None", prompt_data['steps'], sampler,
                     False, False, quantity, batch_size, cfg_scale, prompt_data['seed'],
                     -1, 0, 0, 0, int(width), int(height), "None", None, False, "Seed", "", "Steps", "", [], "", ""],
            "session_hash": "aaa"}

    # todo dont hardcode this
    try:
        print("generating images")
        r = requests.post("http://localhost:7860/api/predict/", json=data)
        # print(r.json())
        encoded_images = r.json()['data'][0]
        if len(encoded_images) > 1:
            encoded_images = encoded_images[1:]

        # decode base64 image to file
        print(f"upscaling {len(encoded_images)} images")
        for i, encoded_image in enumerate(encoded_images):
            # upscale the image
            encoded_images[i] = upscale(encoded_image)

        print("clearing folder")
        # delete all pngs in the folder if the folder exists
        if os.path.exists(folder):
            for file in os.listdir(folder):
                os.remove(folder + "\\" + file)

        # print("saving to file")
        # #save all encoded images to the folder
        # for i, encoded_image in enumerate(encoded_images):
        #     print(i, folder + f'\\{i}.png')
        #     encoded_image = encoded_image.split(",")[1]
        #     # decode base64 image to file
        #     with open(folder + f'\\{i}.png', "wb") as fh:
        #         fh.write(base64.decodebytes(encoded_image.encode()))

        print("adding captions")
        with open(folder + '\\prompt.txt', mode="w") as prompt_file:
            # strip unencoded characters
            prompt_data['prompt'] = prompt_data['prompt'].encode('ascii', 'ignore').decode('ascii')

            prompt_file.write(prompt_data['prompt'])
            if prompt_data['caption']:
                seed = prompt_data['seed']
                for file in encoded_images:
                    # print(file.split(',')[1])
                    add_caption_to_image(base64.decodebytes(file.split(",")[1].encode()), prompt_data['prompt'], model,
                                         time.time() - start_time, prompt_data['quantity'], seed=seed)
                    seed += 1

    except Exception as e:
        # print full stack trace
        import traceback
        traceback.print_exc()
        print(e)
        print("error", str(e))

    return folder


def add_caption_to_all_images_in_folder(folder="", model="", time=0, n=1, seed=""):
    prompt = open(folder + '\\prompt.txt', mode="r").read()
    for file in os.listdir(folder):
        if file.endswith(".png"):
            add_caption_to_image(folder + "\\" + file, prompt, model, time, n)


def add_caption_to_image(file, caption, model="", time=0, n=1, seed=""):
    # put text on the image
    from wand.image import Image as wImage
    from wand.drawing import Drawing
    from wand.font import Font

    # expand the image with a white border
    margin_top = 128 if len(caption) > 50 else 64
    margin_bottom = 16
    margin_left = 16
    margin_right = 16

    with wImage(blob=file) as img:
        # expand the image by margins
        img.border(color='white', width=margin_left, height=margin_top)
        # crop the bottom margin
        img.crop(width=img.width, height=img.height - margin_top + margin_bottom, gravity='north')
        # add the caption to fit in the margin_top
        left, top, width, height = margin_left, 5, img.width - margin_left, margin_top - 10
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

        img.save(filename=folder + "\\" + str(random.randint(0, 1000)) + ".png")


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
        "steps": prompt[11],
        "height": prompt[12],
        "width": prompt[13]
    }
    if prompt is None:
        return seen
    if prompt['output_message_id'] is None and prompt['message_id'] not in seen:
        seen.add(prompt['message_id'])
        # get the discord message from "message_id"
        channel = client.get_channel(prompt['channel_id'])
        message = await channel.fetch_message(prompt['message_id'])

        await message.remove_reaction("😶", client.user)
        await message.remove_reaction("😴", client.user)
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
            caption = interrogate_image(prompt['image_path'], prompt['prompt'])
            if not caption:
                caption = "I don't know."
            new_message = await message.channel.send(caption, reference=message)
            await message.remove_reaction("🤔", client.user)
            await message.add_reaction("✅")

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
        await message.add_reaction("✅")
        await message.remove_reaction("🤔", client.user)

        # update the db row with the output_message_id and set queued to false
        c.execute("UPDATE prompts SET output_message_id = ?, queued = ? WHERE message_id = ?",
                  (new_message.id, False, prompt['message_id']))
        conn.commit()

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


openai.api_key = data['openai']
# run bat file in the background
p = subprocess.call(["start", "webui.bat"], shell=True, cwd=r"Z:/Documents/stable-diffusion-webui/")
print("Waiting for webui to start...", end="")
while True:
    try:
        requests.get("http://localhost:7860/")
        break
    except:
        print(".", end="")
        time.sleep(5)
print("")
client = Client()
client.run(data['token'])
