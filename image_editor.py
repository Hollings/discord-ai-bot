import base64
import io
import json
import random

import discord
import openai
import requests
from discord import File
from dotenv import dotenv_values
from wand.color import Color
from wand.drawing import Drawing
from wand.font import Font
from wand.image import Image as wImage

from models.prompt import Prompt


class ImageData():
    def __init__(self, data: str):
        self.data = data  # a base64 encoded string starting with "data:image/png;base64," prefix

    def save(self, path: str):
        with open(path, "wb") as f:
            # save bytes to file
            f.write(base64.decodebytes(self.data.split(",")[1].encode()))

    def encode_to_discord_file(self) -> File:
        z = self.data[self.data.find(',') + 1:]
        file = discord.File(io.BytesIO(base64.b64decode(z)), filename="image.png")
        return file

    def add_caption_to_image(self, caption: str, subcaption: str = None):
        # expand the image with a white border
        caption_height = 128 if len(caption) > 50 else 64
        sub_caption_height = 16
        margin_horizontal = 0

        with wImage(blob=base64.decodebytes(self.data.split(",")[1].encode())) as img:
            # expand the image by margins
            img.border(color='white', width=margin_horizontal, height=caption_height)
            # crop the bottom margin
            img.crop(width=img.width, height=img.height - caption_height + sub_caption_height, gravity='north')
            # add the caption to fit in the margin_top
            left, top, width, height = margin_horizontal, 5, img.width - margin_horizontal, caption_height - 10
            with Drawing() as context:
                context.fill_color = 'white'
                context.rectangle(left=left, top=top, width=width, height=height)
                font = Font('/System/Library/Fonts/MarkerFelt.ttc')
                context(img)
                img.caption(caption, left=left, top=top, width=width, height=height, font=font, gravity='center')

            # add the subcaption to the bottom margin
            left, top, width, height = 15, img.height - 15, 512, 15
            with Drawing() as context:
                context.fill_color = 'white'
                context.rectangle(left=left, top=top, width=width, height=height)
                font = Font('/System/Library/Fonts/MarkerFelt.ttc', color=Color('#888'))
                context(img)
                img.caption(subcaption, left=left, top=top, width=width,
                            height=height,
                            font=font, gravity='west')

            # convert to base64
            img.format = 'png'
            img_data = img.make_blob()
            encoded = base64.b64encode(img_data).decode('utf-8')
            self.data = "data:image/png;base64," + encoded

    def upscale(self, size=2):
        # print(encoded_image)
        data = {
            "fn_index": 39,
            "data": [
                0,
                self.data,
                None,
                0,
                0,
                0,
                size,
                "Lanczos",
                "None",
                1, [], "", ""
            ],
            "session_hash": "abasbasb"
        }
        r = requests.post("http://localhost:7860/api/predict/", json=data)
        # print(r.json())
        self.data = r.json()['data'][0][0]


def generate_txt_to_img(prompt: Prompt) -> [ImageData]:
    config = dotenv_values('.env')

    prompt_list = json.loads(prompt.prompts)
    prompt_list_text = "\n".join(prompt_list)
    # if every prompt is the same
    if len(set(prompt_list)) == 1:
        prompt_list_text = prompt_list[0]
        quantity = len(prompt_list)
    else:
        quantity = 1
    b64_prompt = base64.b64encode(prompt_list_text.encode()).decode('utf-8')
    b64_prompt = "data:text/plain;base64," + b64_prompt
    data = {"fn_index": 11,
            "data": ["",
                     prompt.negative_prompt,
                     "None",
                     "None",
                     prompt.steps,
                     config['SAMPLER'],
                     False,
                     False,
                     quantity,
                     int(config['BATCH_SIZE']),
                     int(config["CFG_SCALE"]),
                     prompt.seed,
                     -1,
                     0,
                     0,
                     0,
                     False,
                     prompt.width,
                     prompt.height,
                     False,
                     False,
                     0.7,
                     "Prompts from file or textbox",
                     False,
                     False,
                     {'name': "file.txt", "size": len(prompt_list_text) + len(prompt_list) - 1, "data": b64_prompt},
                     "",
                     "Seed",
                     "",
                     "Steps",
                     "",
                     True,
                     False,
                     None],
            "session_hash": "aaa"}

    r = requests.post("http://localhost:7860/api/predict/", json=data)
    encoded_images = r.json()['data'][0]
    return [ImageData(encoded_image) for encoded_image in encoded_images]


def generate_img_to_txt(image_data: ImageData, prompt=None) -> str:
    config = dotenv_values('.env')
    openai.api_key = config['OPENAI_API_KEY']

    data = {"fn_index": 30,
            "data": [image_data.data],
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

                {prompt.prompt}

                """

            response = openai.Completion.create(
                engine="text-davinci-001",
                prompt=choice,
                max_tokens=200,
                temperature=1.0,
                echo=False,
            )['choices'][0]['text']
    return response
