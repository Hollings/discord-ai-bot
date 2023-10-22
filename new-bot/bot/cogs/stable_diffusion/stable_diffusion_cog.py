import random
import re

from celery import Celery
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog

from common import tasks
from cogs.stable_diffusion.prompt import Prompt, PromptStatus


async def setup(bot):
    stable_diffusion = StableDiffusion(bot)


class StableDiffusion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.db.create_tables([Prompt])
        self.app = Celery('tasks')
        print("StableDiffusion cog init")

    # on message
    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.content == "!queue":
            i = self.app.control.inspect()
            queued_tasks = i.reserved()  # Get tasks that are reserved (waiting to be executed)
            num_tasks = sum(len(queued_task) for queued_task in queued_tasks.values()) if queued_tasks else 0
            await message.channel.send(f"Number of tasks in the queue: {num_tasks}")

        if message.content.startswith("!"):
            prompt = self.message_to_prompt(message)
            tasks.text_to_image_task.delay(prompt.id)
            await message.add_reaction("🙄")
        # elif len(message.attachments) > 0:
        #     prompt = self.message_to_prompt(message)
        self.bot.logger.info("on_message")

    async def cog_load(self):
        print("StableDiffusion cog loaded")

    def message_to_prompt(self, message: Message):
        channel_id = message.channel.id  # Get channel id
        message_id = message.id  # Get message id
        message_content = message.content  # Get message content

        negative_prompt, message_content = self.parse_negative_prompt(message_content)
        seed, message_content = self.parse_seed(message_content)
        apply_caption, message_content = self.parse_apply_caption(message_content)
        steps, message_content = self.parse_steps(message_content)
        height, width, message_content = self.parse_size(message_content)
        quantity, message_content = self.parse_quantity(message_content)

        attachment_urls = [attachment.url for attachment in message.attachments]

        new_prompt = Prompt.create(
            text=message_content,
            channel_id=channel_id,
            message_id=message_id,
            seed=seed,
            negative_prompt=negative_prompt,
            apply_caption=apply_caption,
            steps=steps,
            status="pending",
            height=height,
            width=width,
            quantity=quantity,
            attachment_urls=attachment_urls
        )

        return new_prompt

    def parse_negative_prompt(self, message_content):
        if "|" not in message_content:
            return "", message_content
        # split the message content by the last | character
        split_message = message_content.rsplit("|", 1)
        return split_message[1], split_message[0]

    def parse_seed(self, message_content):

        # if a % character exists before the first alphanumeric character, remove it and return a random number
        if re.search(r'%\w', message_content):
            return 42069, re.sub(r'%', '', message_content)

        # Use regular expression to find a number enclosed in curly brackets
        match = re.search(r'\{(\d+)\}', message_content)

        if match:
            # Extract the number from the match object
            number = int(match.group(1))

            # Remove the number (and the enclosing curly brackets) from the string
            modified_string = re.sub(r'\{' + str(number) + r'\}', '', message_content)
            return number, modified_string
        else:
            return random.randint(1, 999), message_content

    def parse_apply_caption(self, message_content):
        # if there is a period before the first alphanumeric character, remove it and return True
        if re.search(r'\.\w', message_content):
            return True, re.sub(r'\.', '', message_content)
        else:
            return False, message_content

    def parse_steps(self, message_content):
        return 30, message_content

    def parse_size(self, message_content):
        return 512, 512, message_content

    def parse_quantity(self, message_content):
        count = 0  # Initialize counter for special characters
        index_to_start = 0  # Initialize index from which to keep the characters

        for i, char in enumerate(message_content):
            # Stop iterating and set the index when an alphanumeric character is found
            if char.isalnum():
                index_to_start = i
                break
            # Increment the counter by 1 if an exclamation mark is found
            elif char == '!':
                count += 1
            # Increment the counter by 5 if a pound sign is found
            elif char == '#':
                count += 5

        # Remove special characters from the beginning
        modified_string = message_content[index_to_start:]

        return count, modified_string
