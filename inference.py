from PIL import Image
import io
import json
import base64
import requests
import re

def resize_image(image_path, output_size=(300, 300)):
    with Image.open(image_path) as img:
        img.thumbnail(output_size)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=img.format)
        return img_byte_arr.getvalue()
    
def encode_image(image_bytes):
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    return encoded_string

encoded_image = encode_image(resize_image("cyclist.png"))

print("Image loaded. Sending Post Request")

controller_url = "http://0.0.0.0:10000/worker_generate_stream" 

data = {
    "prompt": "USER: Describe this image. <image> </s>ASSISTANT:",
    "images": [encoded_image],
    "stop": "</s>",
    "model":"llava-v1.5-13b",
}

response = requests.post(controller_url, json=data, stream=True)
print('response received')

accumulated_response = []
try:
    for chunk in response.iter_lines(decode_unicode=True):
        if chunk:
            # Directly append chunk without manipulation
            decoded_chunk = chunk.decode('utf-8').rstrip('\0')
            accumulated_response.append(decoded_chunk)
    # Join accumulated chunks and then process as a whole
    # complete_response = ''.join(accumulated_response).replace('\0', '')  # Removing null characters globally
    input_string = decoded_chunk.replace('\0','')
    matches = re.findall(r'\{(.*?)\}', input_string)

    # The last match is the content of the last set of curly brackets
    last_match = matches[-1] if matches else None
    print(last_match.strip())

except requests.exceptions.ChunkedEncodingError as e:
    print("Error Reading Stream:", e)
except json.JSONDecodeError as e:
    print("Error Decoding JSON:", e)
