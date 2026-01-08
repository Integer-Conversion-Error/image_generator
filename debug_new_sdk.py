from google import genai
import os

print(dir(genai))
print("Start Client")
try:
    client = genai.Client(api_key="TEST")
    print(dir(client))
    print("Models attribute:")
    print(dir(client.models))
except Exception as e:
    print(e)
