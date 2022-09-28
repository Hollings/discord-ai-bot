import json
import random
import sqlite3
from random import sample, randint, choice

import discord

random_tags = [
    "concept art",
    "renaissance painting",
    "3d render",
    "game art",
    "powerpoint",
    "funny",
    "origami",
    "sketch",
    "anime",
    "inverted colors",
    "reddit",
    "Pop art",
    "Obama Campaign Hope Poster",
    "Starry Night style",
    "The Scream style",
    "Cave drawings",
    "Map",
    "Minecraft",
    "Pixel Art",
    "Spilled milk",
    "Spaghetti",
    "cyberpunk",
    "Wood sculpture",
    "claymation",
    "1950s",
    "1850s",
    "1700s",
    "biblically accurate",
    "minimalist",
    "Picasso style",
    "Ornate",
    "shiny",
    "glowing",
    "Childs drawing",
    "Angelic dreamscape",
    "chaotic and random",
    "feminine",
    "masculine",
    "nonbinary",
    "unreal engine",
    "ukiyo-e",
    "basic bitch",
    "machinery",
    "animal crossing",
    "NES",
    "Text Document",
    "Movie Poster",
    "Magazine cover",
    "desert",
    "arid",
    "studio ghibli",
    "rainbow",
    "happy",
    "summer",
    "fall",
    "winter",
    "spring",
    "breath of the wild",
    "windwaker",
    "tea leaves",
    "8 bit",
    "dark",
    "terrifying",
    "crungus",
    "swamp",
    "Fluid simulation",
    "ugly",
    "forest",
    "leaves",
    "autumn",
    "morning light",
    "single line drawing",
    "MS Paint",
    "macro closeup",
    "copper sculpture",
    "granite sculpture",
    "funfetti",
    "mashed potato sculpture",
    "bee movie",
    "vaporwave",
    "psychedelic",
    "leather",
    "illustration",
    "opalescent surface",
    "isometric",
    "cartoon",
    "cottagecore",
    "anxiety",
    "horror",
    "bloody",
    "dark forest",
    "matte",
    "stoic",
    "fuji-san",
    "cherry blossoms",
    "happy",
    "funeral",
    "yeehaw",
    "The Wiggles",
    "purple hair",
    "shrek",
    "the sims 5",
    "veggie tales",
    "rick and morty",
    "the office",
    "low poly",
    "food art",
    "paint splatter",
    "crop circles",
    "90s Lan",
    "Disposable Camera"
]

quality_tags = [
    "overhead lighting",
    "soft shadows",
    "muted colors",
    "ambient lighting",
    "trending on artstation",
    "studio lighting",
    "official art",
    "nature photography",
    "photography",
    "cinematic",
    "golden hour",
    "sunlight",
    "elegant",
    "deep focus",
    "realistic reflections",
    "sharp focus",
    "DSLR",
    "award winning photography",
    "8k",
    "ultra realistic",
    "forced perspective",
    "highly-detailed",
    "well lit",
    "surreal",
    "digital art",
    "intricate details",
    "award winning",
    "artistic",
    "color",
    "smooth",
    "headshot",
    "dramatic backlighting",
    "200mm",
    "f 1.8 aperture",
    "Kodak Portra 400",
    "product photography",
    "film still",
    "cinematographic",
    "octane render",
    "masterpiece",
    "wallpaper",
    "delicate",
    "sharp",
    "beautiful lighting",
    "brush strokes",
    "Canon",
    "depth of field",
    "35mm",
    "tilt shift photography",
]

artist_tags = [
    "Bob Ross",
    "Bob Kehl",
    "Terry Moore",
    "Steve Mccurry",
    "Timothy Hogan",
    "Christian Aslund",
    "Kait Robinson",
    "Jimmy Nelson",
    "Rehahn",
    "Lee Jeffries",
    "Joe McNally",
    "Erik Almas",
    "Mario Testino"
    "Ansel Adams",
    "Greg Rutkowski",
    "Pablo Picasso",
    "Paul Cezanne",
    "Gustav Klimt",
    "Claude Monet",
    "Marcel Duchamp",
    "Henri Matisse",
    "Jackson Pollock",
    "Andy Warhol",
    "Willem De Kooning",
    "Piet Mondrian",
    "Salvador Dali",
]

with open('config/conf.json') as config_file:
    data = json.load(config_file)
client = discord.Client()

# Todo obviously dont hardcode this
bot_channel_ids = {1016036284206174340: 1, 1016070191949557933: 1, 574450161514708992: 1, 1020447026481213450: 1,
                   1020473974758584351: 1, 1022703575530487858: 1, 1022951067593494589: 1}


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))


def queue_prompt(prompt_data: dict):
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # strip unencoded characters
    prompt_data['prompt'] = prompt_data['prompt'].encode('ascii', 'ignore').decode('ascii')

    c.execute("INSERT INTO prompts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (
                  prompt_data['prompt'],
                  prompt_data['quantity'],
                  prompt_data['channel_id'],
                  prompt_data['message_id'],
                  prompt_data['seed'],
                  prompt_data['image_path'],
                  prompt_data['output_message_id'],
                  prompt_data['model'],
                  prompt_data['negative_prompt'],
                  prompt_data['caption'],
                  True,
                  prompt_data['steps'],
                  prompt_data['height'],
                  prompt_data['width']
              ))
    conn.commit()


def get_or_create_user_setting(user_id, user_name):
    conn = sqlite3.connect('db.sqlite')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    if result:
        return result
    else:
        c.execute("INSERT INTO user_settings (user_id,user_name)values(?,?);", (user_id, user_name))
        conn.commit()
        return get_or_create_user_setting(user_id, user_name)


def set_setting(option, value, user_id):
    available_settings = ['steps', 'size']
    if option not in available_settings:
        return False
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    if option == "size":
        width, height = value.split("x")
        height, width = constrain_height_width(int(height), int(width))
        c.execute("UPDATE user_settings SET height = ?, width = ? WHERE user_id = ?", (height, width, user_id))
    if option == 'steps':
        c.execute("UPDATE user_settings SET steps = ? WHERE user_id = ?", (min(50, value), user_id))
    conn.commit()
    return True


def constrain_height_width(height, width):
    max_pixels = 512 * 512
    current_pixels = height * width
    resize_ratio = max_pixels / current_pixels
    if current_pixels > max_pixels:
        width *= resize_ratio
        height *= resize_ratio
    # round them to the nearest 64
    width = round(width / 64) * 64
    height = round(height / 64) * 64
    return [int(height), int(width)]


@client.event
async def on_message(message: discord.Message):
    user_setting = get_or_create_user_setting(message.author.id, message.author.name)
    if message.content.startswith('/set'):
        parts = message.content.split(' ')
        set = set_setting(parts[1], parts[2], message.author.id)
        if set:
            await message.add_reaction("✅")
        return

    if not message.content.startswith('!') and message.attachments:
        message.content = "!" + message.content

    if message.channel.id not in bot_channel_ids.keys() \
            or message.author == client.user \
            or message.content[0] != "!":
        return

        # Display the current queue
    if message.content == "!help":
        await message.channel.send("""Call the bot with `!`, add modifiers in any order, and your prompt.
        
Modifiers:  
`+` Add high quality tags
`?` Add random tags (weird)
`#` Generate 5 images
`##` Generate 10 images
`^` Generate a lower quality but faster image
`|` Everything after | is negatively weighted
`.` no caption
`%{1234}` Use a specific seed. Omitting the brackets (like `!%prompt`) will use the seed 69420

example prompt:
``` !?%{50}# A photo of a house|windows, doors
```
will generate 5 images of a house with random tags and attempt to avoid windows and doors, using the seed 50.

______
**Changing your settings**
Use `/set` and `size` or `steps` to change your settings. For example, `/set size 512x512` will set your image size to 512x512. `/set steps 10` will set your steps to 10.
The bot will use these settings for future images.
""")

        return

    # defaults
    prompt = message.content
    # Defaults
    added_tags = []
    n = bot_channel_ids[message.channel.id]
    model = "stable-diffusion-v1"
    steps = user_setting['steps']
    seed = random.randint(0, 1000)
    add_artist = False
    prompt, negative_prompt = prompt.split("|") if "|" in prompt else (prompt, "")
    caption = True
    # Loop through the symbols at the start of the message and apply the appropriate settings
    current_char = 1
    while current_char < len(prompt) and prompt[current_char] in "!?+#^$.%{":
        if prompt[current_char] == "!":
            n += 1
        if prompt[current_char] == "?":
            added_tags.append(sample(random_tags, randint(3, 8)))
        if prompt[current_char] == "+":
            steps = 75
            added_tags.append(sample(quality_tags, randint(3, 8)))
            # add a random artist tag at the end
            add_artist = True
        if prompt[current_char] == "#":
            if n < 5:
                n = 5  # a discord message can only have 10 images max
            else:
                n = 10
        if prompt[current_char] == "^":
            n = 1
            steps = round(steps / 2)
        if prompt[current_char] == "$":
            model = "wd-v1-2-full-ema"
        if prompt[current_char] == ".":
            caption = False
        if prompt[current_char] == "%":
            seed = 69420

        if prompt[current_char] == "{" and "}" in prompt[current_char + 1:]:
            num_string = ""
            current_char += 1
            while prompt[current_char] != "}":
                if not prompt[current_char].isdigit():
                    num_string = "69420"
                    break
                num_string += prompt[current_char]
                current_char += 1

            seed = int(num_string)

        current_char += 1

    # append the tags to the prompt
    if added_tags:
        prompt += " - " + " ".join([", ".join(tag) for tag in added_tags])

    if add_artist:
        prompt += ". " + choice(["Photograph ", "Designed ", ""]) + "by " + choice(artist_tags)

    # Remove the starting symbols from the prompt
    prompt = prompt[current_char:]

    # Remove the starting whitespace from the prompt
    prompt = prompt.lstrip()

    # if message has an image, save it
    attachment = None
    if len(message.attachments) == 1:
        attachment = message.attachments[0]
        if attachment.filename.endswith(".png") or attachment.filename.endswith(".jpg"):
            await attachment.save(f"images/{attachment.filename}")
            attachment = f"images/{attachment.filename}"


    # Save it to the queue file
    prompt_data = {
        'prompt': prompt,
        'quantity': min(n, 10),
        'channel_id': message.channel.id,
        'message_id': message.id,
        'seed': seed,
        'image_path': attachment,
        'output_message_id': None,
        'model': model,
        'steps': steps,
        'negative_prompt': negative_prompt,
        'caption': caption,
        'height': user_setting['height'],
        'width': user_setting['width'],
        'user_id': message.author.id,
    }
    queue_prompt(prompt_data)

    # React to signal it's been queued
    await message.add_reaction("😶")


client.run(data['token'])
