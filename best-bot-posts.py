import asyncio
import random
from io import BytesIO

import discord
from dotenv import dotenv_values
from peewee import *
import challonge
from discord.utils import get
import openai
from models.bracket_image import BracketImage

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.reactions = True
intents.message_content = True
client = discord.Client(intents=intents)
db = SqliteDatabase('bot.db')
# load env variables
config = dotenv_values('.env')
openai.api_key = config['OPENAI_API_KEY']

async def get_all_images_in_channel():
    # fetch all images in the discord channel
    # TODO - only add new images to the db
    images = []
    print("getting all images")
    # Get messages in batches of 1000
    last_message_time = None
    while True:
        message = None
        async for message in client.get_channel(int(config['STARBOARD_CHANNEL_ID'])).history(limit=1000, oldest_first=True, after=last_message_time):
            # print(message.content)
            for link in message.content.split("\n"):
                if link.endswith(".png"):
                    BracketImage.create(image_url=link, post_id=message.id)
            last_message_time = message.created_at

        if message is None:
            break

    print(f"got {len(images)} images")
    return images

def update_name_of_all_bracket_images():
    # Uses OCR to add the name field for all images, because the data was incomplete
    import io
    import requests
    import pytesseract
    from PIL import Image
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    print("updating names of all bracket images")
    # get first 10 BracketImages
    for image in BracketImage.select():
        response = requests.get(image.image_url)
        # print( type(response) ) # <class 'requests.models.Response'>
        img = Image.open(io.BytesIO(response.content))

        # crop the top quarter of the image, keeping the top left corner
        img = img.crop((0, 0, img.width, 100))
        # img.show()
        # print( type(img) ) # <class 'PIL.JpegImagePlugin.JpegImageFile'>
        text = pytesseract.image_to_string(img)
        # remove non alphanumeric characters and spaces
        text = ''.join(e for e in text if e.isalnum() or e==" ")
        image.name = text
        print(text)
        image.save()
    print("done naming")

def create_tournament_with_random_selection(n=255, name="asdasdasdasd", url=None):
    # get random 10 BracketImages
    images = BracketImage.select().order_by(fn.Random()).limit(n)

    # create a tournament
    tournament = challonge.tournaments.create(name=name, tournament_type="double elimination", url=url)

    # add participants
    i = 0
    for image in images:
        i+=1
        print(f"adding participant {i}/{n}")
        image_name = image.name if image.name else "???"
        try:
            challonge.participants.create(tournament["id"], image_name, misc=image.id)
        except:
            try:
                challonge.participants.create(tournament["id"], image.name + " " + random.randint(0,10000), misc=image.id)
            except:
                pass

        image.bracket_id = tournament["id"]
        image.save()

    # start the tournament
    challonge.tournaments.start(tournament["id"])
    return tournament["id"]

async def run_tournament(tournament_id):
    # get the open_matches
    tournament_channel = client.get_channel(int(config['TOURNAMENT_CHANNEL_ID']))
    # await tournament_channel.send(f"Starting tournament https://challonge.com/{tournament_id} with {len(challonge.participants.index(tournament_id))} participants")
    participants = challonge.participants.index(tournament_id)
    open_matches = challonge.matches.index(tournament_id, state="open")
    total_matches = challonge.matches.index(tournament_id)
    # randomly shuffle open_matches
    import random
    random.shuffle(open_matches)

    while open_matches:
        for match in open_matches:
            closed_matches = challonge.matches.index(tournament_id, state="complete")
            await run_match(match, participants, tournament_channel, tournament_id, len(closed_matches)+1, len(total_matches))
        open_matches = challonge.matches.index(tournament_id, state="open")
        random.shuffle(open_matches)

    challonge.tournaments.finalize(tournament_id)
    await tournament_channel.send("Tournament finished")
    await tournament_channel.send("https://challonge.com/"+tournament_id)

async def run_match(match, participants, tournament_channel, tournament_id, match_number=0, total_matches=0):
    player1_id = match["player1_id"]
    player2_id = match["player2_id"]
    # get participants based on ids from the participants list
    player1 = next((x for x in participants if x["id"] == player1_id), None)
    player2 = next((x for x in participants if x["id"] == player2_id), None)
    # get the BracketImages from the participants
    player1_bracket_image = BracketImage.get(BracketImage.id == int(player1['misc']))
    player2_bracket_image = BracketImage.get(BracketImage.id == int(player2['misc']))
    # use PIL to put both images side by side
    from PIL import Image
    import io
    import requests
    response1 = requests.get(player1_bracket_image.image_url)
    response2 = requests.get(player2_bracket_image.image_url)
    img1 = Image.open(io.BytesIO(response1.content))
    img2 = Image.open(io.BytesIO(response2.content))
    # create a new image with the same height as the images and double the width
    new_image = Image.new('RGB', (img1.width + img2.width + 50, img1.height))
    # paste the images into the new image
    new_image.paste(img1, (0, 0))
    new_image.paste(img2, (img1.width + 50, 0))
    # new_image.show()
    intro_text = f"""You are an extremely energetic esports commentator working at a live tournament where two images go head to head to determine the best one. The current round is:

Round {match_number}/{total_matches}: `{player1['name']}` vs `{player2['name']}

In your commentary, you must add a little bit of quirky commentary about each image, such as a pun. You say, """
    completion = get_completion(intro_text)
    # strip quotes from the completion
    completion = completion.replace('"', '')
    # await tournament_channel.send(completion)
    # send the image to the tournament channel
    with BytesIO() as image_binary:
        new_image.save(image_binary, 'PNG')
        image_binary.seek(0)
        new_message = await tournament_channel.send(content=completion, file=discord.File(fp=image_binary, filename="bracket.png"))
    # add reactions to the message
    await new_message.add_reaction("🅰️")
    await new_message.add_reaction("🅱️")
    # wait for a minute
    print("waiting")
    await asyncio.sleep(60)
    print("done waiting")

    # count the A and B reactions
    new_message = await new_message.fetch()
    a_reaction_count = get(new_message.reactions, emoji='🅰️').count
    b_reaction_count = get(new_message.reactions, emoji="🅱️").count

    while a_reaction_count+b_reaction_count <= 3:
        print("waiting for more votes")
        await asyncio.sleep(30)
        new_message = await new_message.fetch()
        a_reaction_count = get(new_message.reactions, emoji='🅰️').count
        b_reaction_count = get(new_message.reactions, emoji="🅱️").count

    if a_reaction_count == b_reaction_count:
        await asyncio.sleep(30)
        print("Stalling for tie vote")
        new_message = await new_message.fetch()
        a_reaction_count = get(new_message.reactions, emoji='🅰️').count
        b_reaction_count = get(new_message.reactions, emoji="🅱️").count

    if a_reaction_count > b_reaction_count:
        # player1 won
        winner = player1
        loser = player2
    elif a_reaction_count < b_reaction_count:
        # player2 won
        winner = player2
        loser = player1
    else:
        completion = get_completion(intro_text + completion + f"""
            After the votes are cast, the match is a tie! The match will be replayed later. You say, \"""")

        # strip quotes from the completion
        completion = completion.replace('"', '')
        await tournament_channel.send(completion)
        return
    print(winner["name"] + " won against " + loser["name"])
    completion = get_completion(intro_text + completion + f"""
    After the votes are cast, the winner is `{winner['name']}`! You say, \"""")



    # report the winner
    challonge.matches.update(tournament_id, match["id"], winner_id=winner["id"],
                             scores_csv=f"{a_reaction_count}-{b_reaction_count}")
    # strip quotes from the completion
    completion = completion.replace('"', '')
    await tournament_channel.send(completion)

    print("winner reported")
    await asyncio.sleep(10)

def get_completion(text: str, temp= 0.7):
    try:
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=text,
            max_tokens=100,
            temperature=temp,
            echo=False,
        )['choices'][0]['text']
    except Exception as e:
        print(e)
        return str(e)
    return response

challonge.set_credentials("Hollingsf", config['CHALLONGE_API_KEY'])

@client.event
async def on_ready():
    print('bot.py logged in as {0.user}'.format(client))
    await run_tournament('bestbotpostsrealbracket1')
    await client.close()

client.run(config['DISCORD_TOKEN'])

