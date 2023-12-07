
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog

async def setup(bot):
    starboard = Starboard(bot)


class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.seen_ids = []

    @Cog.listener("on_raw_reaction_add")
    async def on_raw_reaction_add(self, payload):
        # get the starboard channel from the config
        starboard_channel = await self.bot.fetch_channel(int(self.bot.config['STARBOARD_CHANNEL_ID']))

        # get the message from the payload
        message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

        if message.id in self.seen_ids:
            return

        # if the message is in the starboard channel, return
        if message.channel == starboard_channel:
            return

        # if the message is not from a bot, return
        if not message.author.bot:
            return

        # # Check if the message already exists in the starboard channel
        # async for existing_message in starboard_channel.history(limit=100):  # Adjust limit as needed
        #     if f"{message.jump_url}" in existing_message.content:
        #         return  # Message already exists in starboard, so ignore it

        # if the message is in another server, ignore it
        if message.channel.guild != starboard_channel.guild:
            return

        link = message.attachments[
            0].url if message.attachments else f"> **{message.author.name}**: {message.content}"
        self.seen_ids.append(message.id)
        await starboard_channel.send(f"{message.jump_url}\n{link}")