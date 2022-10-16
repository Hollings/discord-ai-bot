# discord-stable-diffusion (AKA Hollingsbot 2)

![img.png](img.png)

Hollingsbot 2 is a Discord bot that interfaces with [AUTOMATIC1111's web UI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) to generate Stable Diffusion
images on demand.

## Features

- Generate one or more Stable Diffusion images from a prompt in whitelisted discord channels
- Use modifiers in the Discord message to add tags to the prompt, generate more images, change steps, etc
- Automatic upscaling of generated images
- Generate text from an uploaded image

![image](https://user-images.githubusercontent.com/3793509/193608535-2eb98e0f-99fa-4132-8636-71e1aaec4d93.png)

## Install and Run

- Install [AUTOMATIC1111's web UI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
  - **Note** - the A1111 repo gets updated very frequently and new versions may break compatibility with this bot. The
    current commit that the bot has been tested on is `c8045c5ad4f99deb3a19add06e0457de1df62b05`
- Create and invite your discord bot to a server (https://discord.com/developers/applications/)
- (optional, allows the bot to describe uploaded images) Create an OpenAI account and generate an API
  key (https://beta.openai.com/account/api-keys)
- rename `.env.example` to `.env` and update values with the appropriate values
- run `bot.py`

