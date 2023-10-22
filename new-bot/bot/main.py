import logging
import os

import discord
from discord.ext import commands
from dotenv import dotenv_values
from peewee import PostgresqlDatabase

from cogs.starboard.starboard_cog import Starboard


class HollingsBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        config = dotenv_values('.env')
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
        from cogs.stable_diffusion.stable_diffusion_cog import StableDiffusion

        bot.logger.info(f"{bot.user.name} is now online!")
        if "StableDiffusion" not in bot.cogs:
            await bot.add_cog(StableDiffusion(bot))
        if "Starboard" not in bot.cogs:
            await bot.add_cog(Starboard(bot))

    bot.run(bot.config['DISCORD_TOKEN'])



