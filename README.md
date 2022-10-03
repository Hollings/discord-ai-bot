# discord-stable-diffusion (AKA Hollingsbot 2)

![img.png](img.png)

Hollingsbot 2 is a Discord bot that interfaces with [AUTOMATIC1111's web UI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) to generate Stable Diffusion
images on demand.

## Features

- Generate one or more Stable Diffusion images from a prompt in whitelisted discord channels
- Use modifiers in the Discord message to add tags to the prompt, generate more images, change steps, etc
- Generate text from an uploaded image

## Install and Run

- Install [AUTOMATIC1111's web UI](https://github.com/AUTOMATIC1111/stable-diffusion-webui)
- Create and invite your discord bot to a server (https://discord.com/developers/applications/)
- Create an OpenAI account and generate an API key (https://beta.openai.com/account/api-keys)
- rename `.env.example` to `.env` and update values with your OpenAI and Discord API keys
- run `bot.py` (first time running, modify init_db() with `init_db(migrate=True)`to create the database)
- run `bot-generator.py`
- run AUTOMATIC1111's web UI
- **Alternatively, run `run.bat` to run all three scripts in one window**
