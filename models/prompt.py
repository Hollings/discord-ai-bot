import json
from random import sample, randint, random, choice

from peewee import *

db = SqliteDatabase('bot.db')


class Prompt(Model):
    prompts = TextField(null=True)  # json list of prompts
    quantity = IntegerField(default=1)
    channel_id = IntegerField()
    message_id = IntegerField()
    seed = IntegerField(default=-1)
    image_paths = TextField(default="[]")
    output_message_id = IntegerField(null=True)
    model = TextField(default="stable-diffusion-v1")
    sampler = TextField(default="Euler a")
    negative_prompt = TextField(default="(worst quality:0.5), cartoon, halftone print, burlap,(cinematic:0.8), (verybadimagenegative_v1.3:0.15), (surreal:0.4), (modernism:0.5), (art deco:0.3), (art nouveau:0.3)")
    apply_caption = BooleanField(default=True)
    status = TextField(default="pending")
    steps = IntegerField(default=30)
    height = IntegerField(default=512)
    width = IntegerField(default=512)
    options = TextField(default="{}")

    def __repr__(self):
        return self.prompts

    def __str__(self):
        return self.prompts

    class Meta:
        database = db

    def generate_random_tags_list(self, num_tags):

        # Load the JSON file
        with open('e621_tags.json', 'r') as f:
            tags = json.load(f)

        # Create a dictionary to keep track of tags with colons
        colon_tags = []

        # Create a list to store the selected tags
        selected_tags = []
        # shuffle the tags and pick the first one that starts with "artist
        artist_tags = [tag for tag in tags.keys() if tag.startswith("artist")]
        selected_tags.append(choice(artist_tags))


        # # Iterate over the tags in random order
        # for tag in sample(list(tags.keys()), num_tags):
        #     # If the tag contains a colon
        #     if ':' in tag:
        #         # Get the prefix before the colon
        #         prefix = tag.split(':')[0]
        #
        #         # If the prefix is already in colon_tags, use its value
        #         if prefix in colon_tags:
        #             continue
        #         # Otherwise, select a random value and add it to colon_tags
        #         else:
        #             colon_tags.append(prefix)
        #             # Add the tag with the selected value to the list
        #             selected_tags.append(tag)
        #     # If the tag does not contain a colon, simply add it to the list
        #     else:
        #         selected_tags.append(tag)

        # Return a random selection of num_tags from the selected tags list
        return selected_tags

    def apply_modifiers(self):
        current_char = 1
        added_tags = []
        add_artist = False
        prompt = self.prompts
        add_random_tags = 0
        add_quality_tags = 0
        control_mode = 1
        if self.channel_id != 1022703575530487858:
            self.negative_prompt = "(nude, sexy, naked, porn, sex, tits, ass, pussy:0.5), " + self.negative_prompt

        if "|" in prompt:
            # if "|" is not in between [], it's a modifier
            if not ("[" in prompt and "]" in prompt and prompt.index("[") < prompt.index("|") < prompt.index("]")):
                prompt, added_negative_prompt = str(self.prompts).split("|", 1)
                self.negative_prompt = f"({added_negative_prompt}), {self.negative_prompt}"

        # load tags.json
        with open('config/tags.json') as tags_file:
            tags = json.load(tags_file)

        while current_char < len(str(prompt)) and prompt[current_char] in "!?+#^$.%{^<":
            if prompt[current_char] == "!":
                self.quantity += 1
            if prompt[current_char] == "?":
                control_mode += 1
                # constrain control mode to 0,1,2
                control_mode = min(control_mode, 2)
            if prompt[current_char] == "+":
                self.steps = 75
            if prompt[current_char] == "#":
                self.quantity += 5
            if prompt[current_char] == ".":
                self.apply_caption = False
            if prompt[current_char] == "%":
                self.seed = 69420
            if prompt[current_char] == "^":
                self.height += 128
                self.width -= 128
            if prompt[current_char] == "<":
                self.height -= 128
                self.width += 128
            if prompt[current_char] == "{" and "}" in prompt[current_char + 1:]:
                num_string = ""
                current_char += 1
                while prompt[current_char] != "}":
                    if not prompt[current_char].isdigit():
                        num_string = "69420"
                        break
                    num_string += prompt[current_char]
                    current_char += 1
                self.seed = int(num_string)
            current_char += 1

        # if height or width is 0, reset it to 768x768
        if self.height <= 0 or self.width <= 0:
            self.height = 768
            self.width = 768

        self.quantity = min(self.quantity, 10)
        prompt = prompt[current_char:]

        self.options = json.dumps({'control_mode': control_mode})

        # append the tags to the prompt
        added_tags = []
        if add_quality_tags:
            added_tags.append(sample(tags['quality'], randint(2, 5)))
        if add_random_tags:
            selected_tags = self.generate_random_tags_list(10)
            # added_tags.append(sample(selected_tags, randint(1, 8)))
            added_tags.append(selected_tags)
        if add_artist:
            added_tags.append(sample(tags['artist'], 1))
        if added_tags:
            prompt += ". " + " ".join([", ".join(tag) for tag in added_tags])
        self.prompts = prompt

    def generate_img_to_txt(self):
        if not self.image_paths:
            return "Prompt has no image"
