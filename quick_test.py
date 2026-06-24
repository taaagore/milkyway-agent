import os
import traceback
from dotenv import load_dotenv
from google import genai
from PIL import Image

load_dotenv()

try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    img = Image.open("test1.jpg")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=["Read any number visible in this image.", img]
    )
    print("SUCCESS:", response.text)
except Exception as e:
    print("FAILED WITH:")
    traceback.print_exc()