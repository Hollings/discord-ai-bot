import os
import random
from pathlib import Path

import nltk
from discord import File
from dotenv import dotenv_values
import openai
from bark import SAMPLE_RATE, generate_audio, preload_models, semantic_to_waveform
from bark.generation import generate_text_semantic
from scipy.io.wavfile import write
import numpy as np

def generate_ai_audio(input_text):
    voice = random.choice(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
    print("Generating audio with voice: " + voice)
    speech_file_path = Path(__file__).parent / f"speech-{voice}.mp3"
    response = openai.audio.speech.create(
        model="tts-1-hd",
        voice=voice,
        input=input_text
    )

    response.stream_to_file(speech_file_path)

    with open(speech_file_path, "wb") as f:
        f.write(response.content)

    # To return as a Discord file object
    discord_file = File(speech_file_path)
    return discord_file
    # pip install soundfile
    # pip install PySoundFile
# config = dotenv_values('.env')
# openai.api_key = config['OPENAI_API_KEY']
# generate_ai_audio("test test test test")
