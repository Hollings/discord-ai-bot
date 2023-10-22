import openai
from dotenv import dotenv_values

config = dotenv_values('.env')
openai.api_key = config['OPENAI_API_KEY']


def get_chat_completion(prompt, system_message = None, previous_messages = None, model="gpt-3.5-turbo"):
    messages = [
        {"role": "user", "content": prompt},
    ]

    if previous_messages:
        messages += previous_messages
    if system_message:
        messages.insert(0, {"role": "system", "content": system_message})

    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=1.0
    )

    return response.choices[0].message.content, response.usage.total_tokens