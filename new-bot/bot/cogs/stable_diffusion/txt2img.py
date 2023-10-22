import base64
import random

import requests
from PIL.Image import Image


from PIL import Image, ImageDraw, ImageFont
from dotenv import dotenv_values
from cogs.stable_diffusion.prompt import Prompt
import io

def a1_image_gen(prompt: Prompt):
    config = dotenv_values('.env')
    print("generating prompt: " + prompt.text)
    data = {
        "enable_hr": True,
        "denoising_strength": 0.45,
        "hr_scale": 2,
        "hr_second_pass_steps": 5,
        "hr_upscaler": "ESRGAN_4x",
        "prompt": prompt.text,
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

    # if prompt.attachment_urls:
    #     # image_paths is an array of b64 images
    #     # get the first one
    #
    #     prompt_options = json.loads(prompt.options)
    #     data_to_append = {
    #         "controlnet": {
    #             "args": [
    #                 {
    #                     "enabled": True,
    #                     "module": "none",
    #                     "model": "control_v1p_sd15_qrcode_monster_v2 [5e5778cb]",
    #                     "weight": prompt_options.get("control_weight", 1),
    #                     "image": image_paths[0],
    #                     "resize_mode": 1,
    #                     "lowvram": False,
    #                     "processor_res": 512,
    #                     "guidance_start": 0.0,
    #                     "guidance_end": 1.0,
    #                     "control_mode": 0,
    #                     "pixel_perfect": False
    #                 }
    #             ]
    #         }
    #     }
    #     data["alwayson_scripts"] = data_to_append

    r = requests.post(f"{config['GRADIO_API_BASE_URL']}sdapi/v1/txt2img", json=data)
    try:
        files = r.json()["images"]
    except:
        print(r)
        print(r.json())
        return []
    return files


def get_generation_from_api(prompt) -> Image:
    images = a1_image_gen(prompt)
    return images

def batch_add_caption(generated_images, prompt):
    font_size = 40
    caption_size = 75
    # Assuming 'image' is your 768x768 PIL image
    width, height = generated_images[0].size

    # Create a new image with padding at the top
    new_height = height + caption_size
    captioned_images = []

    for generated_image in generated_images:
        new_image = Image.new("RGB", (width, new_height), "white")

        # Initialize ImageDraw
        draw = ImageDraw.Draw(new_image)

        # Load font
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()

        # Text to draw
        text = prompt.text

        # Calculate text width and height
        text_width = draw.textlength(text, font)

        # Calculate X, Y position of the text
        x = (width - text_width) // 2
        y = (caption_size - font_size) // 2

        # Draw text
        draw.text((x, y), text, font=font, fill="black")
        # Paste the original image into the new image
        new_image.paste(generated_image, (0, caption_size))
        captioned_images.append(new_image)
    return captioned_images


def text_to_image(prompt: Prompt):
    generated_images = get_generation_from_api(prompt)

    # convert the b64 encoded images to PIL images
    generated_images = [Image.open(io.BytesIO(base64.b64decode(image))) for image in generated_images]

    captioned_images = batch_add_caption(generated_images, prompt)
    return captioned_images