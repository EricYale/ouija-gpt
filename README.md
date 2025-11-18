# ouija-gpt
Ouija board that actually works, using OpenAI transcription and completions APIs.

## Getting Started
1. Build the hardware. 3D print and laster cutting files are available in `CAD` directory. Wire the stepper and servo motors to the ports indicated in the code.
2. Download code in `ouija-esp32/ouija-esp32.ino` folder to your board. Make sure to include the `ESP32Servo` library (binary included in this repo).
3. In the `ouija-code` directory, install all required dependencies with `pip3` and run `python3 ouija.py`. You may need to change the serial port variable at the top depending on what port your hardware is plugged into.
