import json
from random import sample, randint, random, choice

from peewee import *

db = SqliteDatabase('bot.db')


class Prompt(Model):
    prompt = TextField(null=True)
    quantity = IntegerField(default=1)
    channel_id = IntegerField()
    message_id = IntegerField()
    seed = IntegerField(default=-1)
    image_paths = TextField(default="[]")
    output_message_id = IntegerField(null=True)
    model = TextField(default="stable-diffusion-v1")
    sampler = TextField(default="Euler a")
    negative_prompt = TextField(default="")
    apply_caption = BooleanField(default=True)
    queued = BooleanField(default=True)
    steps = IntegerField(default=40)
    height = IntegerField(default=512)
    width = IntegerField(default=512)

    def __repr__(self):
        return self.prompt

    def __str__(self):
        return self.prompt

    class Meta:
        database = db

    def apply_modifiers(self):
        current_char = 1
        added_tags = []
        add_artist = False

        if "|" in self.prompt:
            self.prompt, self.negative_prompt = str(self.prompt).split("|")

        # load tags.json
        with open('config/tags.json') as tags_file:
            tags = json.load(tags_file)

        while current_char < len(str(self.prompt)) and self.prompt[current_char] in "!?+#^$.%{":
            if self.prompt[current_char] == "!":
                self.quantity += 1
            if self.prompt[current_char] == "?":
                added_tags.append(sample(tags['random'], randint(1, 3)))
            if self.prompt[current_char] == "+":
                self.steps = 75
                added_tags.append(sample(tags['quality'], randint(2, 5)))
                # add a random artist tag 50% of the time at the end
                add_artist = random() > 0.5
            if self.prompt[current_char] == "#":
                self.quantity += 5
            if self.prompt[current_char] == "^":
                self.quantity = 1
                self.steps = round(self.steps / 2)
            if self.prompt[current_char] == ".":
                self.apply_caption = False
            if self.prompt[current_char] == "%":
                self.seed = 69420
            if self.prompt[current_char] == "{" and "}" in self.prompt[current_char + 1:]:
                num_string = ""
                current_char += 1
                while self.prompt[current_char] != "}":
                    if not self.prompt[current_char].isdigit():
                        num_string = "69420"
                        break
                    num_string += self.prompt[current_char]
                    current_char += 1
                self.seed = int(num_string)
            current_char += 1

        # append the tags to the prompt
        if added_tags:
            self.prompt += " - " + " ".join([", ".join(tag) for tag in added_tags])

        if add_artist:
            self.prompt += ". " + choice(["Photograph ", "Designed ", ""]) + "by " + choice(tags['artist'])

        self.prompt = self.prompt[current_char:]

    def generate_img_to_txt(self):
        if not self.image_paths:
            return "Prompt has no image"
