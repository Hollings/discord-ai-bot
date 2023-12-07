import datetime
import random
import re
import sys

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
        self.modifier_methods = [
            self.check_dalle,
            self.parse_negative_prompt,
            self.parse_seed,
            # self.parse_apply_caption,
            self.parse_steps,
            # self.parse_size,
            self.parse_quantity,
        ]
    # on message
    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.content == "!unstick":
            tasks.queue_all_pending_prompts_task()
            return

        if str(message.channel.id) not in self.bot.config["STABLE_DIFFUSION_CHANNEL_IDS"].split(","):
            return

        if message.content == "!queue":
            i = self.app.control.inspect()
            queued_tasks = i.reserved()  # Get tasks that are reserved (waiting to be executed)
            num_tasks = sum(len(queued_task) for queued_task in queued_tasks.values()) if queued_tasks else 0
            await message.channel.send(f"Number of tasks in the queue: {num_tasks}")
            return

        if message.attachments:
            for attachment in message.attachments:
                # Check if the attachment is a text file
                if attachment.filename.endswith('.txt'):
                    await self.create_gif_prompt_from_text_file_message(message)
                    await message.add_reaction("🙄")
                    return
        if not message.content.startswith("!"):
            return
        if message.content.startswith("!*"):
            return


        # check for <1,2,3> syntax
        # Pattern to find the bracketed section
        bracket_pattern = re.compile(r"<(.*?)>")
        bracket_match = bracket_pattern.search(message.content)
        double_bracket_pattern = re.compile(r"<<(.*?)>>")
        double_bracket_match = double_bracket_pattern.search(message.content)

        try:
            if double_bracket_match:
                await self.create_gif_prompt_from_message(message)
            elif bracket_match:
                await self.create_image_multi_prompt_from_message(message)
            else:
                prompt = self.message_to_prompt(message)
                tasks.create_text_to_image_task(prompt)
        except Exception as e:
            # get full dump
            _, _, tb = sys.exc_info()
            file_name = tb.tb_frame.f_code.co_filename
            line_number = tb.tb_lineno
            await message.channel.send(f"Exception occurred at {file_name}:{line_number}\n\n{e}")
            await message.add_reaction("❌")
            return

        await message.add_reaction("🙄")

    async def create_gif_prompt_from_text_file_message(self, message):
        # get the contents of the txt file
        attachment = message.attachments[0]
        attachment_content = await attachment.read()
        attachment_content = attachment_content.decode("utf-8")
        # split the contents by word
        words = attachment_content.split()
        window_size = len(words) - 30
        parent_prompt = None
        for i in range(len(words) - window_size + 1):
            sliding_window_string = ' '.join(words[i:i + window_size])
            prompt = self.message_to_prompt(message, sliding_window_string[:400],
                                            parent_prompt=parent_prompt)  # Replace with your method
            if not parent_prompt:
                parent_prompt = prompt
            prompt.seed = parent_prompt.seed
            prompt.save()

        tasks.create_text_to_image_task(parent_prompt)

    async def create_image_multi_prompt_from_message(self, message):
        bracket_pattern = re.compile(r"<(.*?)>")
        bracket_match = bracket_pattern.search(message.content)
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

    async def create_gif_prompt_from_message(self, message):
        double_bracket_pattern = re.compile(r"<<(.*?)>>")
        double_bracket_match = double_bracket_pattern.search(message.content)
        words = double_bracket_match.group(1).split(",")
        if len(words) == 2:
            words.append("20")
        if len(words) == 1:
            words = ["0","20","20"]
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

        def count_decimal_places(number):
            number_str = str(number)
            if '.' in number_str:
                return len(number_str.split('.')[1])
            return 0

        current_decimal_places = count_decimal_places(current)
        end_decimal_places = count_decimal_places(end)

        max_decimal_places = max(current_decimal_places, end_decimal_places) + 2

        frames = words[2]
        rounding_format = '0.' + '0' * max_decimal_places
        frames = Decimal((end - current) / frames).quantize(Decimal(rounding_format))
        frames = Decimal(str(frames).rstrip('0').rstrip('.'))

        while current <= end:
            full_prompt = base_message.format(current)
            prompt = self.message_to_prompt(message, full_prompt,
                                            parent_prompt=parent_prompt)  # Replace with your method
            if not parent_prompt:
                parent_prompt = prompt
            prompt.seed = parent_prompt.seed
            prompt.save()

            current += frames
        tasks.create_text_to_image_task(parent_prompt)

    async def cog_load(self):
        print("ImageGen cog loaded")


    def message_to_prompt(self, message: Message, prompt_text_override=None, parent_prompt=None):
        channel_id = message.channel.id  # Get channel id
        message_id = message.id  # Get message id
        message_content = prompt_text_override if prompt_text_override else message.content  # Get message content

        message_content, modifiers = self.parse_modifiers(message_content, message)
        attachment_urls = [attachment.url for attachment in message.attachments]
        method = "dalle3" if modifiers['dalle'] else "stable-diffusion"

        new_prompt = Prompt.create(
            method=method,
            text=message_content,
            channel_id=channel_id,
            message_id=message_id,
            user_id=message.author.id,
            seed=modifiers["seed"],
            negative_prompt=modifiers["negative_prompt"],
            apply_caption=False,
            steps=modifiers["steps"],
            status="pending",
            height=512,
            width=512,
            quantity=modifiers["quantity"],
            attachment_urls=attachment_urls,
            parent_prompt=parent_prompt,
        )

        return new_prompt

    def check_dalle(self, message_content, modifiers, message=None):
        if not message_content.startswith("$$$") or not message:
            return message_content, modifiers


        user_id = str(message.author.id)
        minutes = 30 #todo use a setting here
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
                                .order_by(Prompt.created_at.asc())
                                .get()).created_at

            next_available_time = last_prompt_time + datetime.timedelta(minutes=minutes)
            remaining_time = next_available_time - datetime.datetime.now()
            readable_time = divmod(remaining_time.total_seconds(), minutes)

            if remaining_time.total_seconds() > 0:
                raise Exception(
                    f"Dalle is on cooldown for {message.author.nick}. Try again in {readable_time[0]:.0f} minutes and {readable_time[1]:.0f} seconds.")
        modifiers['dalle'] = True
        return message_content[3:], modifiers

    def parse_quantity(self, message_content, modifiers, message=None):
        if message_content.startswith('!'):
            if 'quantity' in modifiers:
                modifiers['quantity'] += 1
            else:
                modifiers['quantity'] = 1
            message_content = message_content[1:]

        if message_content.startswith('#'):
            if 'quantity' in modifiers:
                modifiers['quantity'] += 4
            else:
                modifiers['quantity'] = 4
            message_content = message_content[1:]
        return message_content, modifiers

    def parse_seed(self, message_content, modifiers, message=None):
        if message_content.startswith('%'):
            modifiers['seed'] = 69420
            message_content = message_content[1:]
        elif message_content.startswith('{') and '}' in message_content:
            # Use regular expression to find a number enclosed in curly brackets and the rest of the string
            match = re.search(r'\{(\d+)\}(.*)', message_content)
            if match:
                # Extract the number and set it as the seed in modifiers
                number = int(match.group(1))
                modifiers['seed'] = number

                # Update message_content to include only the part to the right of the bracketed section
                message_content = match.group(2).strip()

        return message_content, modifiers

    def parse_negative_prompt(self, message_content, modifiers, message=None):
        # Replace all '|' inside square brackets with a placeholder
        placeholder = "PLACEHOLDER"
        modified_content = re.sub(r'(\[.*?])', lambda x: x.group().replace('|', placeholder), message_content)

        # Split the modified content by '|'
        split_message = modified_content.split('|', 1)

        if len(split_message) == 2:
            rest, negative_prompt = split_message
            # Restore the placeholder in both parts
            negative_prompt = negative_prompt.replace(placeholder, '|')
            rest = rest.replace(placeholder, '|')
            modifiers['negative_prompt'] = negative_prompt.strip()
            message_content = rest

        return message_content.strip(), modifiers

    def parse_steps(self, message_content, modifiers, message=None):
        if message_content.startswith('+'):
            modifiers['steps'] += 2
            message_content = message_content[1:]
        elif message_content.startswith('-'):
            modifiers['steps'] -= 2
            modifiers['steps'] = max(1, modifiers['steps'])
            message_content = message_content[1:]
        return message_content, modifiers


    def parse_modifiers(self, message_content, message=None):

        modifiers = {
            "seed": random.randint(0, 1000),
            "steps": 20,
            "dalle": False,
            "negative_prompt": "",
        }

        for i in range(20):
            original_value = modifiers.copy()
            for modifier_method in self.modifier_methods:
                message_content, modifiers = modifier_method(message_content=message_content, modifiers=modifiers, message=message)

            if modifiers == original_value:
                break

        return message_content, modifiers