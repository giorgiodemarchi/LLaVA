from PIL import Image
import io
import json
import base64
import requests
import re
import cv2 
import time 
import subprocess
import threading

import openai

max_gpu_memory_usage = 0

def sample_gpu_memory_usage(interval=1):
    """Periodically samples GPU memory usage."""
    global max_gpu_memory_usage
    while True:
        # Run the nvidia-smi command to get the current GPU memory usage
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], stdout=subprocess.PIPE)
        current_usage = int(result.stdout.decode('utf-8').strip())
        
        # Update the maximum GPU memory usage observed
        max_gpu_memory_usage = max(max_gpu_memory_usage, current_usage)
        
        # Wait for the specified interval before sampling again
        time.sleep(interval)

def get_gpu_metrics():
    """Returns the current GPU memory usage by querying nvidia-smi."""
    memory_usage_query = ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits']
    utilization_query = ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits']
    
    memory_result = subprocess.run(memory_usage_query, stdout=subprocess.PIPE)
    utilization_result = subprocess.run(utilization_query, stdout=subprocess.PIPE)
    
    gpu_memory_usage = memory_result.stdout.decode('utf-8').strip()
    gpu_utilization = utilization_result.stdout.decode('utf-8').strip()
    
    return gpu_memory_usage, gpu_utilization



def read_video(video_path, freq):
    """
    video_path: can also be a URL
    freq: frequency of extracted frames. E.g. if freq = 5, one frame every 5 seconds is extracted
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        exit()

    # frame rate of the video
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps

    extracted_frames = []
    
    if freq < duration:
        skip_frames = int(fps * freq)   
        # Extract a frame every <freq> secs
        frame_count = 0
        while True:
            success, frame = cap.read()
            if not success:
                break  # Exit the loop if we've reached the end of the video

            # Check if this frame is at a <freq>-second interval
            if frame_count % skip_frames == 0:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame)
                extracted_frames.append(pil_img)

            frame_count += 1 
    
    else:
        # Extract the middle frame of the video
        middle_frame_index = total_frames // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_index)
        success, frame = cap.read()
        if success:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame)
            extracted_frames.append(pil_img)

    cap.release()
    cv2.destroyAllWindows()
    return extracted_frames


def resize_and_encode_image(image, output_size=(300, 300)):
    image.thumbnail(output_size)
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='png')
    image_bytes = img_byte_arr.getvalue()
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    return encoded_string


def predict(video_file, mode, controller_url = "http://0.0.0.0:10000/worker_generate_stream", freq = 5):
    """
    video_file: either a local file or a url
    mode: "SFX" / "AMBIENCE" / "CAPTION"
    controller_url: 
    freq: frequency of frames extraction from video.

    TODO: Scene splitting and logic to provide multiple scenes
    """
    frames = read_video(video_file, freq)

    encoded_images = [resize_and_encode_image(image) for image in frames]
    number_of_images = len(encoded_images)
    print(number_of_images)

    image_token_string = ""
    for _ in range(number_of_images):
        image_token_string += "<image> "

    # prompt = f"USER: Here are {number_of_images} frames extracted from a video, in chronological order. Describe what is happening in the video. {image_token_string} </s>ASSISTANT:"
    prompt = f"USER: Here are {number_of_images} frames extracted from a video, in chronological order: {image_token_string}."
    if mode == 'CAPTION':
        prompt += "Describe what is happening in the video. </s> ASSISTANT:"
    else:
        # prompt += "I want you to assist me in desining the best sound for this video. Using your understanding of what is happening in the video, including actions, objects, and scene, answer the following question: "
        if mode == 'SFX':
            prompt += "Provide 4 possible background sound effects or ambience sounds that would fit the video well. </s> ASSISTANT:" # with a description suitable for searching in a sound library. </s> ASSISTANT:"
        else:
            prompt += "What ambience sounds would you expect to hear when watching the video? Provide a description suitable for searching in a sound library. </s> ASSISTANT:"

    data = {
        "prompt": prompt,
        "images": encoded_images,
        "stop": "</s>",
        "model": "llava-v1.5-13b",
    }

    headers = {"User-Agent": "LLaVA Client"}

    response = requests.post(controller_url, json=data, headers = headers, stream=True)
    # print(response.text)

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
        last_match = matches[-1].strip() if matches else None
        final_answer = last_match.split("ASSISTANT:")[1].split("\", \"error_code\"")[0]

        return final_answer

    except requests.exceptions.ChunkedEncodingError as e:
        print("Error Reading Stream:", e)
    except json.JSONDecodeError as e:
        print("Error Decoding JSON:", e)
    except Exception as e:
        print(e)
    return "ERROR"

if __name__ == "__main__":

    # GPU monitoring
    gpu_memory_before, gpu_utilization_before = get_gpu_metrics()
    print(f"GPU Memory Usage Before: {gpu_memory_before} MB")
    thread = threading.Thread(target=sample_gpu_memory_usage, args=(1,), daemon=True)
    thread.start()
    
    # Time
    start_time = time.time()
    video_file = 'cyclist.mp4'  # Can also be a url
    
    controller_url = "http://0.0.0.0:10000/worker_generate_stream"
    freq = 15
    mode = "SFX"

    answer = predict(video_file, mode, controller_url = controller_url, freq = freq)
    print(answer)

    openai_key = "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"
    #openai.api_key = openai_key

    client = openai.OpenAI(api_key = openai_key)

    if answer.strip()[-1]!='.':
        n_sounds = 3
    else:
        n_sounds = 4
    response = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    response_format={ "type": "json_object" },
    messages=[
        {"role": "system", "content": "You are a helpful assistant designed to output JSON. For each 'sound' in the JSON, there must be two attributes: 'name' and 'description'."},
        {"role": "user", "content": f"Given the following text describing {n_sounds} sounds, provide a detailed audio description that will be used as the prompt to an audio generation model, and a short name with two to five words. {answer}. "}
    ]
    )
    gpt_response_json = json.loads(response.choices[0].message.content)
    print(response.choices[0].message.content)
    suggestions_list = [{'name': sound['name'], 'description': sound['description']} for sound in gpt_response_json['sounds']]

    print(type(suggestions_list[0]))
    print(len(suggestions_list))
    for suggestion in suggestions_list:
        print(suggestion['name'])
        print(suggestion['description'])


    # Time
    end_time = time.time()
    print(f"Execution time: {end_time - start_time} seconds")
    # GPU
    gpu_memory_after, gpu_utilization_after = get_gpu_metrics()
    memory_difference = int(gpu_memory_after) - int(gpu_memory_before)
    utilization_difference = int(gpu_utilization_after) - int(gpu_utilization_before)
    print(f"Memory Difference: {memory_difference} MB")
    print(f"Utilization Difference: {utilization_difference}%")
    print(f"Maximum GPU Memory Usage: {max_gpu_memory_usage} MB")
