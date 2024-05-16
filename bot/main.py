import logging
import os

import discord
from discord.ext import commands
from dotenv import dotenv_values
from peewee import PostgresqlDatabase

from common import tasks


class HollingsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        config = dotenv_values('.env')
        config["SYSTEM_PROMPT"] = config.get("SYSTEM_PROMPT", "")
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        super().__init__(*args, **kwargs)
        self.config = config
        self.logger = logger

def initialize_bot():
    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    intents.reactions = True
    intents.message_content = True
    intents.members = True

    bot = HollingsBot(command_prefix="|", intents=intents)
    bot.db = PostgresqlDatabase('postgres', user='postgres', password='postgres',
                               host='postgres', port=5432)
    bot.logger.info("Initialized bot")
    return bot

if __name__ == "__main__":
    bot = initialize_bot()

    # Load the cog from the specified file
    @bot.event
    async def on_ready():
        from cogs.image_gen.image_gen_cog import ImageGen
        from cogs.starboard.starboard_cog import Starboard
        from cogs.gpt_chat.gpt_chat_cog import GptChat
        from cogs.tts.tts_cog import Tts
        from cogs.gpt_vision.gpt_vision_cog import GptVision


        bot.logger.info(f"{bot.user.name} is now online!")
        if "ImageGen" not in bot.cogs:
            await bot.add_cog(ImageGen(bot))
        if "Starboard" not in bot.cogs:
            await bot.add_cog(Starboard(bot))
        if "GptChat" not in bot.cogs:
            await bot.add_cog(GptChat(bot))
        if "Tts" not in bot.cogs:
            await bot.add_cog(Tts(bot))
        if "GptVision" not in bot.cogs:
            await bot.add_cog(GptVision(bot))

        tasks.clear_queue()
        tasks.queue_all_pending_prompts_task()


    @bot.event
    async def on_message(message):
        if message.content == "!restart":
            await bot.reload_extension("cogs.image_gen.stable_diffusion_cog")
            await bot.reload_extension("cogs.starboard.starboard_cog")
            await bot.reload_extension("cogs.gpt_chat.gpt_chat_cog")
            await message.channel.send("Reloaded all cogs")

    bot.run(bot.config['DISCORD_TOKEN'])



