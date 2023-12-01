import base64
import random
import textwrap

import openai
import requests
from PIL.Image import Image

from PIL import Image, ImageDraw, ImageFont
from dotenv import dotenv_values
import io

from cogs.image_gen.prompt import Prompt


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

    r = requests.post(f"{config['GRADIO_API_BASE_URL']}sdapi/v1/txt2img", json=data)
    try:
        files = r.json()["images"]
    except:
        print(r)
        print(r.json())
        return []
    return files


def dalle_image_gen(prompt: Prompt):
    print("generating DALLE prompt: " + prompt.text)
    config = dotenv_values('.env')
    openai.api_key = config['OPENAI_API_KEY']
    try:
        images = openai.images.generate(
            model="dall-e-3",
            prompt=prompt.text,
            n=1,
            size="1024x1024",
            response_format="b64_json",
        )
    except:
        return [], prompt.text

    return [images.data[0].b64_json], images.data[0].revised_prompt


def get_generation_from_api(prompt) -> Image:
    images = []
    revised_prompt = ""
    # images = a1_image_gen(prompt)
    if prompt.method == "stable-diffusion":
        images = a1_image_gen(prompt)
    elif prompt.method == "dalle3":
        images, reworded_prompt = dalle_image_gen(prompt)
        revised_prompt = reworded_prompt
    return images, revised_prompt if prompt.method == "dalle3" else prompt.text


def calculate_font_size(caption):
    if len(caption) < 100:
        return 40
    elif len(caption) < 200:
        return 30
    return 20


def add_caption_to_image(img, caption, output_path):
    # Font settings

    font_size = calculate_font_size(caption)
    font_path = "arial.ttf"
    font = ImageFont.truetype(font_path, font_size)

    # Create a temporary drawing context to calculate text size
    temp_img = Image.new('RGB', (img.width, img.height), (255, 255, 255))
    temp_draw = ImageDraw.Draw(temp_img)

    # Calculate text size and wrap text
    margin = 20
    max_width = img.width - 2 * margin
    wrapped_text = textwrap.fill(caption, width=100)
    text_bbox = temp_draw.textbbox((0, 0), wrapped_text, font=font)
    wrap_count = 100
    while text_bbox[2] > max_width:
        wrap_count -= 1
        wrapped_text = textwrap.fill(caption, width=wrap_count)
        text_bbox = temp_draw.textbbox((0, 0), wrapped_text, font=font)

    # Calculate the height of the caption and create a new image with space for caption
    caption_height = text_bbox[3] + 2 * margin
    new_img = Image.new('RGB', (img.width, img.height + caption_height), (255, 255, 255))
    new_img.paste(img, (0, caption_height))

    # Draw the text onto the new image, centered
    draw = ImageDraw.Draw(new_img)
    text_width = text_bbox[2] - text_bbox[0]
    x = (new_img.width - text_width) // 2
    y = margin
    draw.text((x, y), wrapped_text, fill="black", font=font)

    # Save the new image
    return new_img


def batch_add_caption(generated_images, prompt):
    captioned_images = []

    for generated_image in generated_images:
        captioned_images.append(add_caption_to_image(generated_image, prompt.text, "temp.png"))
    return captioned_images


def text_to_image(prompt: Prompt):
    generated_images, revised_prompt = get_generation_from_api(prompt)
    if len(generated_images) == 0:
        return [], ""
    # convert the b64 encoded images to PIL images
    generated_images = [Image.open(io.BytesIO(base64.b64decode(image))) for image in generated_images]

    captioned_images = batch_add_caption(generated_images, prompt)
    return captioned_images, revised_prompt
