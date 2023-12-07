import asyncio

import openai
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog, Context


async def setup(bot):
    gpt_vision = GptVision(bot)


class GptVision(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("GPT Chat cog init")

    # on message
    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.channel.id != int(self.bot.config["GPT_CHAT_CHANNEL_ID"]):
            return

        if message.author.bot:
            return

        if len(message.attachments):
            # send typing indicator
            ctx = await self.bot.get_context(message)
            typing_task = asyncio.create_task(self.send_typing_indicator_delayed(ctx))
            message_content_task = asyncio.create_task(self.get_gpt_vision_response(message))
            content = await message_content_task
            # Wait for the typing task to complete if it's still running
            typing_task.cancel()
            await message.channel.send(content)

    async def send_typing_indicator_delayed(self, ctx: Context):
        timer = asyncio.sleep(2)
        await timer
        try:
            for i in range(15):
                async with ctx.channel.typing():
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def cog_load(self):
        print("GPT Chat cog loaded")

    async def get_gpt_vision_response(self, message: Message):
        openai.api_key = self.bot.config['OPENAI_API_KEY']

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": message.content},
                    {
                        "type": "image_url",
                        "image_url": f"{message.attachments[0].url}"
                    },
                ],
            }
        ]

        if self.bot.config["SYSTEM_PROMPT"]:
            messages.insert(0, {"role": "system", "content": self.bot.config["SYSTEM_PROMPT"]})

        response = openai.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=500,
        )
        response_text = response.choices[0].message.content
        await message.channel.send(response_text[:1999])
