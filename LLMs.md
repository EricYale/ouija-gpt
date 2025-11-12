# Instructions for LLMs

## Project Description

I'm making a functional Ouija board using the OpenAI transcriptions and completions APIs.

**Hardware**: the enclosure consists of a 3D-printed box with a laser-engraved top. The top is made out of wood and has engraved "yes", "no", "maybe" labels arranged on the left, bottom, and right of a circle respectively. A servo motor rotates a magnet on a stick around each stop on this circle, so that a paper clip "moves by itself" to each yes/no/maybe label when the magnet moves. Additionally, there is a stepper motor connected to a physical spinner that indicates when the LLM is thinking.

**Technical details**: `ouija-code/ouija.py` runs on a Raspberry Pi and handles the OpenAI calls. It communicates via serial to an ESP32 that's connected to the servo and stepper motors. Code for the ESP32 is in `esp32/ouija.ino`.

**States**: When the Python program is ready, it starts listening via USB mic. It uses the Streaming Transcriptions API to pass audio data realtime to OpenAI. This API uses a webhook, and is able to indicate when an utterance finishes. Each time an utterance finishes, the transcribed text is passed to the Completions Structured Data API to get a "yes", "no", "maybe", or "invalid" response, which indicates the supposed spirits' response to the user's spoken question. The prompt for this should live in a separate file, `ouija-code/prompt.txt`. The user should be able to interrupt any time, and the latest utterance will be processed.
When a "yes", "no", or "maybe" response is received, the servo motor immediately moves the magnet to the correct position. If the last state is the same as the new state, the magnet briefly moves to a different position for 0.4 seconds before settling on the correct answer. The user should be able to interrupt any time, and the latest utterance will be processed.

**Control of the spinner**: The spinner will rotate slowly counterclockwise while it is awaiting a user utterance to finish. When the utterance finishes, it will start spinning rapidly clockwise to indicate the LLM is thinking. When the answer comes from OpenAI, the spinner stops. Finally, after the servo motor moves to indicate the spirits' response, the spinner goes back to rotating slowly counterclockwise.

## Example Code
Motor control:

```ino
#include <ESP32Servo.h>
#include <Stepper.h>

Stepper myStepper(2048, 12, 14, 27, 26);
Servo servo;

void setup() {
  myStepper.setSpeed(5);
  servo.attach(25);
}

int servoPos = 0;
void loop() {
  myStepper.step(100);
  servo.write(servoPos);
  servoPos += 10;

  if(servoPos > 180) {
    servoPos = 0;
    servo.write(0);
  }

  delay(15);
}
```

Serial communication:
```py
import time
import serial

ser = serial.Serial("/dev/ttyUSB0", 115200)

while True:
    # Read lines from serial until there's none left
    while ser.in_waiting:
        line = ser.readline().decode('utf-8').rstrip()
        print(line)
    time.sleep(0.01)
```

## Code Style
- Do not add comments to your code
- When making python variable names, do not use excessive abbreviations or anything that would make the code hard to read
- Do not use any Python virtual environments. If necessary, install pip3 packages to the system.
- Use `pip3` and `python3` instead of `pip` and `python`.