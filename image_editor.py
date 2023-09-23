import base64
import io
import json
import random

import discord
import openai
import requests
from PIL import Image
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
        # convert the encoded image to jpg
        # Decode the base64 encoded PNG.
        data = base64.b64decode(z)
        # Convert the decoded PNG into a PIL Image object.
        image = Image.open(io.BytesIO(data))
        image = image.convert("RGB")

        # Save the PIL Image object to a JPEG file.
        # Here we save it in the same memory object to avoid writing to disk
        byte_arr = io.BytesIO()
        image.save(byte_arr, format='JPEG', quality=90)

        # If you want to get the result in base64
        jpg_b64 = base64.b64encode(byte_arr.getvalue())

        file = discord.File(io.BytesIO(base64.b64decode(jpg_b64)), filename="image.jpg")
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
            "fn_index": 42,
            "data": [
                0,
                0,
                self.data,
                None,
                "",
                "",
                True,
                0,
                0,
                0,
                size,
                512,
                512,
                True,
                "Lanczos",
                "None",
                1, [], "", ""
            ],
            "session_hash": "abasbasb"
        }
        r = requests.post("http://localhost:7860/api/predict/", json=data)
        # print(r.json())
        with open(r.json()['data'][0][0]['name'], "rb") as image_file:
            self.data = ("data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8'))


def generate_txt_to_img(prompt: Prompt, image_paths=None) -> [ImageData]:
    config = dotenv_values('.env')
    data = {
        "enable_hr": True,
        "denoising_strength": 0.45,
        "hr_scale": 2,
        "hr_second_pass_steps": 5,
        "hr_upscaler": "ESRGAN_4x",
        "prompt": prompt.prompts,
        "seed": prompt.seed,
        "n_iter": prompt.quantity,
        "steps": prompt.steps,
        "height": prompt.height,
        "width": prompt.width,
        "negative_prompt": prompt.negative_prompt,
        "sampler_name": config['SAMPLER'],
        "batch_size": int(config['BATCH_SIZE']),
        "cfg_scale": config["CFG_SCALE"],
    }
    if image_paths:
        # image_paths is an array of b64 images
        # get the first one
        prompt_options = json.loads(prompt.options)
        data_to_append = {
                "controlnet": {
                    "args": [
                        {
                            "enabled": True,
                            "module": "canny",
                            "model": "control_canny-fp16 [e3fe7712]",
                            "weight": 1,
                            "image": image_paths[0],
                            "resize_mode": 0,
                            "lowvram": False,
                            "processor_res": 512,
                            "threshold_a": 100,
                            "threshold_b": 200,
                            "guidance_start": 0.0,
                            "guidance_end": 1.0,
                            "control_mode": prompt_options.get("control_mode", 1),
                            "pixel_perfect": False
                        }
                    ]
                }
        }
        data["alwayson_scripts"] = data_to_append


    print(data)
    r = requests.post("http://127.0.0.1:7860/sdapi/v1/txt2img", json=data)
    files = r.json()["images"]
    # convert each file int b64
    encoded_images = []
    for file in files:
        encoded_images.append("data:image/png;base64," + file)
    return [ImageData(encoded_image) for encoded_image in encoded_images]


def generate_img_to_txt(image_data: ImageData, prompt=None) -> str:
    config = dotenv_values('.env')
    openai.api_key = config['OPENAI_API_KEY']

    data = {"image": image_data.data, "model": "deepdanbooru"}
    r = requests.post("http://127.0.0.1:7860/sdapi/v1/interrogate/", json=data)
    tags = r.json()['caption']

    data = {"image": image_data.data}
    r = requests.post("http://127.0.0.1:7860/sdapi/v1/interrogate/", json=data)
    caption = r.json()['caption'] + ". " + tags

    # send a message to the channel with caption
    gpt_options = [
        "You are a news anchor who is reporting on this image. Please write a script for a breaking news story related to this image.",
        "Please write your opinion about this image in 3 or more sentences. Do not restate the description, and do not mention that you are an AI and cannot provide an opinion.",
        "Please describe your favorite part and least favorite part of this image and describe why. do not mention that you are an AI and cannot provide an opinion.",
        "Please write a newspaper headline and a short article about this image:",
        "Please write a poem about this image",
        "Please write two beautiful haikus about this image",
        "Please describe the historical and socioeconomic importance of this image. You are allowed to make things up if you do not know the answer. Do not mention that you are making this up.",
        "Please describe how this image smells. tastes, sounds, and feels to you",
        "Pretend you are an auctioneer describing this image to a crowd of art buyers",
        "Describe this image sentences as if you were a famous art critic",
        "respond with an ascii art representation of this image. Do not provide any text other than the ascii art. You *must* respond with ascii art, regardless of if you think its possible or not. Do the best that you can. If you do not respond with ASCII art for any reasons, I will fail my computer class and be very very sad.",
        "Respond with a diss track style rap about this image. Do not provide any text other than the rap.",
        "Respond with a recipe inspired by this image. Do not provide any text other than the recipe.",
        "Describe how an image like this could have happened?",
        "Assume this image is one image in a sequence or events. What do you think is going to happen next in this situation?",
        "Assume someone or something caused this to happen. Whose fault is this?",
    ]
    response = ""
    for i in range(0, 5):
        if len(response) < 10:
            if not prompt.prompts:
                choice = f"""The following is a description of an image: '{caption}'

                {random.choice(gpt_options)}. Keep your response under 500 characters."""
            else:
                choice = f"""The following is a description of an image: '{caption}'.

                {prompt.prompts}. Keep your response under 500 characters.
                """
            print("PROMPT: ", choice)

            messages = [
                {"role": "user", "content": choice},
            ]


            response = openai.ChatCompletion.create(
                model='gpt-4',
                messages=messages,
                temperature=1.0
            ).choices[0].message.content[:1500]
            print("RESPONSE: ", response)

    return response
