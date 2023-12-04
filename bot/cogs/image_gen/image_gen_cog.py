import datetime
import random
import re

from decimal import Decimal
from celery import Celery
from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog

from common import tasks
from cogs.image_gen.prompt import Prompt, PromptStatus


async def setup(bot):
    image_gen = ImageGen(bot)


class ImageGen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # bot.db.drop_tables([Prompt])
        bot.db.create_tables([Prompt])
        self.app = Celery('tasks')
        print("Image Gen cog init")

    # on message
    @Cog.listener("on_message")
    async def on_message(self, message):
        if str(message.channel.id) not in self.bot.config["STABLE_DIFFUSION_CHANNEL_IDS"].split(","):
            return

        if message.content == "!queue":
            i = self.app.control.inspect()
            queued_tasks = i.reserved()  # Get tasks that are reserved (waiting to be executed)
            num_tasks = sum(len(queued_task) for queued_task in queued_tasks.values()) if queued_tasks else 0
            await message.channel.send(f"Number of tasks in the queue: {num_tasks}")
            return

        if message.content.startswith("!") and not message.content.startswith("!*"):

            # check for <1,2,3> syntax
            # Pattern to find the bracketed section
            bracket_pattern = re.compile(r"<(.*?)>")
            bracket_match = bracket_pattern.search(message.content)
            double_bracket_pattern = re.compile(r"<<(.*?)>>")
            double_bracket_match = double_bracket_pattern.search(message.content)


            if double_bracket_match:
                words = double_bracket_match.group(1).split(",")
                if len(words) == 2:
                    words.append("1")

                if len(words) != 3:
                    await message.channel.send("invalid gif syntax, use <<from, to, step>> or <<from, to>>")
                    return


                # Convert each word to decimal
                words = [Decimal(word.strip()) for word in words]

                # Base message without the bracketed section
                base_message = double_bracket_pattern.sub("{}", message.content)
                full_prompt = base_message.format(words[0])
                parent_prompt = None

                # Use Decimal in the range-like function
                current = words[0]
                end = words[1]
                step = words[2]
                while current <= end:
                    full_prompt = base_message.format(current)
                    prompt = self.message_to_prompt(message, full_prompt,
                                                    parent_prompt=parent_prompt)  # Replace with your method
                    if not parent_prompt:
                        parent_prompt = prompt
                    prompt.seed = parent_prompt.seed
                    prompt.save()

                    current += step
                tasks.create_text_to_image_task(parent_prompt)
            elif bracket_match:
                # Extract words within the brackets
                words = bracket_match.group(1).split(",")
                # Base message without the bracketed section
                base_message = bracket_pattern.sub("{}", message.content)

                # Iterate over each word and generate an image
                for word in words:
                    word = word.strip()
                    full_prompt = base_message.format(word)
                    prompt = self.message_to_prompt(message, full_prompt)  # Replace with your method
                    tasks.create_text_to_image_task(prompt)


            else:
                try:
                    prompt = self.message_to_prompt(message)
                    tasks.create_text_to_image_task(prompt)
                except Exception as e:
                    await message.channel.send(str(e))
                    await message.add_reaction("❌")
                    return
            await message.add_reaction("🙄")

    async def cog_load(self):
        print("ImageGen cog loaded")

    def message_to_prompt(self, message: Message, prompt_text_override=None, parent_prompt=None):
        channel_id = message.channel.id  # Get channel id
        message_id = message.id  # Get message id
        message_content = prompt_text_override if prompt_text_override else message.content  # Get message content

        negative_prompt, message_content = self.parse_negative_prompt(message_content)
        seed, message_content = self.parse_seed(message_content)
        # apply_caption, message_content = self.parse_apply_caption(message_content)
        steps, message_content = self.parse_steps(message_content)
        height, width, message_content = self.parse_size(message_content)
        quantity, message_content = self.parse_quantity(message_content)

        attachment_urls = [attachment.url for attachment in message.attachments]

        method = "dalle3" if self.check_dalle(message) else "stable-diffusion"
        if method == "dalle3":
            message_content = message_content.replace("$$$", "")

        new_prompt = Prompt.create(
            method=method,
            text=message_content,
            channel_id=channel_id,
            message_id=message_id,
            user_id=message.author.id,
            seed=seed,
            negative_prompt=negative_prompt,
            apply_caption=False,
            steps=steps,
            status="pending",
            height=height,
            width=width,
            quantity=quantity,
            attachment_urls=attachment_urls,
            parent_prompt=parent_prompt,
        )

        return new_prompt

    def check_dalle(self, message: Message, minutes=45):
        if "$$$" not in message.content:
            return False
        user_id = str(message.author.id)

        one_hour_ago = datetime.datetime.now() - datetime.timedelta(minutes=minutes)

        try:
            prompt_count = (Prompt.select()
                            .where((Prompt.user_id == user_id) &
                                   (Prompt.method == "dalle3") &
                                   (Prompt.created_at > one_hour_ago))
                            .count())

        except Exception as e:
            # Handle any other exceptions
            raise e

        if prompt_count >= 3:
            # Calculate the time until the user can use Dalle again
            last_prompt_time = (Prompt.select(Prompt.created_at)
                                .where((Prompt.user_id == user_id) &
                                       (Prompt.method == "dalle3"))
                                .order_by(Prompt.created_at.desc())
                                .get()).created_at

            next_available_time = last_prompt_time + datetime.timedelta(minutes=minutes)
            remaining_time = next_available_time - datetime.datetime.now()
            readable_time = divmod(remaining_time.total_seconds(), minutes)

            if remaining_time.total_seconds() > 0:
                raise Exception(
                    f"Dalle is on cooldown for {message.author.nick}. Try again in {readable_time[0]:.0f} minutes and {readable_time[1]:.0f} seconds.")

        return True

    def parse_negative_prompt(self, message_content):
        # Replace all '|' inside square brackets with a placeholder
        placeholder = "PLACEHOLDER"
        modified_content = re.sub(r'(\[.*?])', lambda x: x.group().replace('|', placeholder), message_content)

        # Split the modified content by '|'
        split_message = modified_content.split('|', 1)

        if len(split_message) == 2:
            rest, negative_prompt  = split_message
            # Restore the placeholder in both parts
            negative_prompt = negative_prompt.replace(placeholder, '|')
            rest = rest.replace(placeholder, '|')
            return negative_prompt, rest
        else:
            return "", message_content

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
        return 20, message_content

    def parse_size(self, message_content):
        return 512, 512, message_content

    def parse_quantity(self, message_content):
        count = 0  # Initialize counter for special characters
        index_to_start = 0  # Initialize index from which to keep the characters

        for i, char in enumerate(message_content):
            # Stop iterating and set the index when an character that isnt ! or # is found

            # Increment the counter by 1 if an exclamation mark is found
            if char == '!':
                count += 1
            # Increment the counter by 5 if a pound sign is found
            elif char == '#':
                count += 5
            else:
                index_to_start = i
                break
        # Remove special characters from the beginning
        modified_string = message_content[index_to_start:]

        return count, modified_string
