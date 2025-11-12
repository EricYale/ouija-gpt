import openai
import serial
import sounddevice as sd
import asyncio
import websockets
import json
import os
import numpy as np
import sys
import base64
import time

# --- Configuration ---
SERIAL_PORT = "/dev/cu.usbserial-130"  # Adjust as needed
BAUD_RATE = 115200
AUDIO_DEVICE = None  # Use default device
SAMPLE_RATE = 24000
CHANNELS = 1
BLOCK_SIZE = 1024
TRANSCRIPTION_WEBSOCKET_URL = "wss://api.openai.com/v1/realtime?intent=transcription"
PROMPT_FILE = os.path.join(os.path.dirname(__file__), 'prompt.txt')
MIN_AUDIO_BYTES = SAMPLE_RATE * 2 * 0.1  # 0.1 seconds of audio

# --- Global State ---
ser = None
utterance_text = ""
is_utterance_finished = False
last_valid_responses = []

def setup_serial():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE)
        print("Serial connection established.")
        set_spinner_state('s')
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        print("Running in simulation mode. Motor commands will be printed.")
        ser = None

def send_serial_command(command):
    if ser:
        ser.write(command.encode('utf-8'))
    else:
        print(f"Simulated serial command: {command}")

def set_spinner_state(state):
    print("Setting spinner state to:", state)
    send_serial_command(state)

def move_planchette(response):
    if response == "yes":
        send_serial_command('y')
    elif response == "no":
        send_serial_command('n')
    elif response == "maybe":
        send_serial_command('m')
    # 'invalid' responses do not move the planchette

async def audio_input_stream(queue):
    """Capture audio and put it into the queue."""
    def callback(indata, frames, time, status):
        if status:
            print(status)
        volume_norm = np.linalg.norm(indata) * 10
        # print(f'Volume: {volume_norm}', end='\r')
        sys.stdout.flush()
        queue.put_nowait(bytes(indata))

    with sd.InputStream(
        device=AUDIO_DEVICE,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16',
        blocksize=BLOCK_SIZE,
        callback=callback
    ):
        print("Listening for questions...")
        while True:
            await asyncio.sleep(0.1)

async def transcribe_audio(audio_queue):
    global utterance_text, is_utterance_finished
    
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}"
    }

    # Silence / speech detection parameters
    silence_threshold = 300  # empirical RMS threshold
    max_silence_seconds = 1.2
    last_voice_time = time.time()
    have_spoken = False
    pending_commit = False

    try:
        async with websockets.connect(TRANSCRIPTION_WEBSOCKET_URL, additional_headers=headers) as ws:
            print("Connected to OpenAI Realtime Transcription WebSocket.")

            session_update = {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {
                                "type": "audio/pcm",
                                "rate": SAMPLE_RATE,
                            },
                            "noise_reduction": {
                                "type": "far_field"
                            },
                            "transcription": {
                                "language": "en",
                                "model": "whisper-1"
                            },
                            "turn_detection": {
                                "type": "semantic_vad",
                                "create_response": True,
                                "eagerness": "high",
                                "interrupt_response": True
                            }
                        }
                    }
                }
            }
            await ws.send(json.dumps(session_update))
            audio_buffer = bytearray()

            async def sender():
                nonlocal last_voice_time, have_spoken, pending_commit, audio_buffer
                while True:
                    try:
                        audio_bytes = await audio_queue.get()
                        if not audio_bytes:
                            continue
                        audio_buffer += audio_bytes
                        if len(audio_buffer) < MIN_AUDIO_BYTES:
                            continue
                        
                        b64_audio = base64.b64encode(audio_buffer).decode()
                        append_msg = {"type": "input_audio_buffer.append", "audio": b64_audio}
                        await ws.send(json.dumps(append_msg))

                        audio_buffer = bytearray()
                        if have_spoken and (time.time() - last_voice_time) > max_silence_seconds and not pending_commit:
                            pending_commit = True
                            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                            await ws.send(json.dumps({"type": "response.create", "response": {"modalities": ["text"], "instructions": "transcribe"}}))
                    except asyncio.CancelledError:
                        break

            async def receiver():
                global utterance_text, is_utterance_finished
                nonlocal pending_commit, have_spoken
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue
                    # print(data)
                    msg_type = data.get("type")
                    if msg_type == "input_audio_buffer.speech_started":
                        set_spinner_state('t')
                    elif msg_type == "input_audio_buffer.speech_stopped":
                        set_spinner_state('s')
                    elif msg_type == "conversation.item.input_audio_transcription.completed":
                        set_spinner_state('s')
                        utterance_text = data.get("transcript", "")
                        is_utterance_finished = True
                        pending_commit = False
                        have_spoken = False
                    elif msg_type == "error":
                        print(f"Realtime error: {data.get('error')}")

            await asyncio.gather(asyncio.create_task(sender()), asyncio.create_task(receiver()))
    except Exception as e:
        print(f"WebSocket connection failed: {e}")

def get_spirit_response(question, context_messages=None):
    try:
        with open(PROMPT_FILE, 'r') as f:
            prompt = f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {PROMPT_FILE}")
        return "invalid"

    try:
        client = openai.OpenAI()
        messages = [{"role": "system", "content": prompt}]
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": question})
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=5,
            temperature=0.5,
        )
        answer = response.choices[0].message.content.strip().lower()
        if answer in ["yes", "no", "maybe", "invalid"]:
            return answer
        else:
            return "invalid" # Default to invalid if response is not one of the expected
    except Exception as e:
        print(f"Error getting completion from OpenAI: {e}")
        return "invalid"

async def main_loop():
    global utterance_text, is_utterance_finished, last_valid_responses
    
    setup_serial()
    
    audio_queue = asyncio.Queue()
    
    audio_task = asyncio.create_task(audio_input_stream(audio_queue))
    transcription_task = asyncio.create_task(transcribe_audio(audio_queue))

    while True:
        if is_utterance_finished:
            print(f"Utterance finished: '{utterance_text}'")
            set_spinner_state('s')

            # Prepare context for spirit response
            context_messages = []
            for pair in last_valid_responses[-7:]:
                context_messages.append({"role": "user", "content": pair[0]})
                context_messages.append({"role": "assistant", "content": pair[1]})

            response = get_spirit_response(utterance_text, context_messages)
            print(f"Spirit response: {response}")

            if response != "invalid":
                last_valid_responses.append((utterance_text, response))
                if len(last_valid_responses) > 7:
                    last_valid_responses = last_valid_responses[-7:]
                last_state = None
                if len(last_valid_responses) > 1:
                    last_state = last_valid_responses[-2][1]
                if last_state == response:
                    alt = next(s for s in ["yes", "no", "maybe"] if s != response)
                    move_planchette(alt)
                    await asyncio.sleep(0.1)
                move_planchette(response)
                await asyncio.sleep(2)

            # Reset for next utterance
            utterance_text = ""
            is_utterance_finished = False

        await asyncio.sleep(0.1)

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
    else:
        try:
            asyncio.run(main_loop())
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            if ser and ser.is_open:
                ser.close()
