import json

import openai

async def respond_gpt(message, client):
    openai.api_key = client.config['OPENAI_API_KEY']

    # get message content
    message_content = message.content
    # get channel id
    channel_id = message.channel.id
    # get the last 10 messages in the channel
    channel = message.channel
    messages = [message async for message in message.channel.history(limit=5)]
    formatted_messages = format_chat_history(messages, client.config.get("SYSTEM_PROMPT", ""))
    # get the last message that was not sent by the bot
    print(formatted_messages)
    # Make the API request
    response = openai.chat.completions.create(
        response_format={"type": "json_object"},
        model="gpt-4-1106-preview",
        messages=formatted_messages,
        max_tokens=800,
    )
    print(response.choices[0].message.content)
    json_data = json.loads(response.choices[0].message.content)
    try:
        await message.add_reaction(json_data["emoji"])
    except:
        print("failed adding emoji")
        pass
    await message.channel.send(json_data["content"][:1999])

def format_chat_history(messages, system_prompt="") -> list:
    formatted_messages = [{"role": "system", "content": "Respond as you normally would, but in the following JSON format: {'emoji': '✅', 'content': 'your message'} the emoji key is anything that you want it to be. Use it to convey emotion, confusion, or anything else. Leave this blank unless you feel its absolutely relevant and necessary. There are multiple users in this chat, the speaker will be identified before each of their message content. Don't copy the 'message author' type formatting in your response. just reply normally.\n\n IMPORTANT Follow these instructions exactly: " + system_prompt}]
    # Take the last 10 messages from the chat history
    total_chars = 0
    for message in messages:
        total_chars += len(message.content)
        if total_chars > 5000:
            break
        role = "assistant" if message.author.bot else "user"
        formatted_messages.insert(0, {"role": role, "content": f"(message author: '{message.author.display_name}') {message.content}"})
    return formatted_messages