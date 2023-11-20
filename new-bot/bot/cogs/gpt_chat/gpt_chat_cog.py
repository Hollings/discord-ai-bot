import asyncio
import json
import random
import re

import openai
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog


async def setup(bot):
    gpt_chat = GptChat(bot)


class GptChat(commands.Cog):
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

        if message.content == "!system":
            await message.channel.send("Current System Prompt: ```" + self.bot.config.get("SYSTEM_PROMPT", "(none)") + "```")
            return

        if message.content.startswith("!system "):
            system_prompt = message.content.replace("!system", "").strip()
            if system_prompt == "reset":
                system_prompt = ""
            self.bot.config["SYSTEM_PROMPT"] = system_prompt
            await message.channel.send("Current System Prompt: ```" + self.bot.config.get("SYSTEM_PROMPT", "(none)") + "```")
            return

        if len(message.attachments) > 0:
            # let the gpt-v cog handle this
            return

        # send typing indicator
        typing_task = asyncio.create_task(self.send_typing_indicator_delayed(message))
        message_content_task = asyncio.create_task(self.get_gpt_chat_response(message))
        content = await message_content_task
        # Wait for the typing task to complete if it's still running
        typing_task.cancel()
        await message.channel.send(content)


    async def send_typing_indicator_delayed(self, message):
        timer = asyncio.sleep(1)
        async with message.channel.typing():
            await asyncio.sleep(20)
            await timer

    async def cog_load(self):
        print("GPT Chat cog loaded")

    async def get_gpt_chat_response(self, message: Message):
        openai.api_key = self.bot.config['OPENAI_API_KEY']

        messages = [message async for message in message.channel.history(limit=5)]
        formatted_messages = self.format_chat_history(messages, self.bot.config.get("SYSTEM_PROMPT", ""))
        # Make the API request
        response = openai.chat.completions.create(
            response_format={"type": "json_object"},
            model="gpt-4-1106-preview",
            messages=formatted_messages,
            max_tokens=800,
        )
        json_data = json.loads(response.choices[0].message.content)
        reaction_coroutine = message.add_reaction(json_data["emoji"])
        await message.channel.send(json_data["content"][:1999])
        await reaction_coroutine

    def format_chat_history(self, messages, system_prompt="") -> list:
        formatted_messages = [{"role": "system",
                               "content": "Respond as you normally would, but in the following JSON format: {'emoji': '✅', 'content': 'your message'} the emoji key is anything that you want it to be. Use it to convey emotion, confusion, or anything else. Leave this blank unless you feel its absolutely relevant and necessary. There are multiple users in this chat, the speaker will be identified before each of their message content. Don't copy the 'message author' type formatting in your response. just reply normally.\n\n IMPORTANT Follow these instructions exactly: " + system_prompt}]
        # Take the last 10 messages from the chat history
        total_chars = 0
        for message in messages:
            total_chars += len(message.content)
            if total_chars > 5000:
                break
            role = "assistant" if message.author.bot else "user"
            member = message.guild.get_member(message.author.id)
            nickname = member.nick if member else message.author.name

            formatted_messages.insert(0, {"role": role,
                                          "content": f"(message author: '{nickname}') {message.content}"})
        return formatted_messages