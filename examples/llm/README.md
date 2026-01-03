# LLM Voice Assistant Example

This example demonstrates a voice-interactive AI assistant using [Qwen](https://github.com/QwenLM/Qwen) LLM with dora-rs. It captures speech, transcribes it, generates responses with Qwen, and speaks the response back.

## Overview

The dataflow creates a complete voice assistant pipeline:

```
microphone -> VAD -> Whisper (STT) -> Qwen (LLM) -> Kokoro (TTS) -> speaker
                                          |
                                          v
                                       rerun (display)
```

### Nodes

- **dora-microphone**: Captures audio from your microphone
- **dora-vad**: Voice Activity Detection - detects when you're speaking
- **dora-distil-whisper**: Speech-to-Text using Distil-Whisper model
- **dora-qwen**: Large Language Model (Qwen) for generating responses
- **dora-kokoro-tts**: Text-to-Speech using Kokoro for voice output
- **dora-pyaudio**: Plays audio through your speakers
- **plot**: Visualizes conversation in Rerun viewer using `dora-rerun`

## Prerequisites

- Python 3.11+
- dora-rs
- Microphone and speakers
- Sufficient GPU/RAM for running LLM locally (or API access)

### System Dependencies

#### macOS

```bash
brew install portaudio
brew install espeak-ng
```

#### Linux

```bash
sudo apt-get install portaudio19-dev
sudo apt-get install espeak
```

## Getting Started

### 1. Install dora

```bash
# Install dora CLI
cargo install dora-cli

# Install Python package (must match CLI version)
pip install dora-rs
```

**Important**: Ensure the `dora` CLI version matches the `dora-rs` Python package version:

```bash
dora --version      # Check CLI version
pip show dora-rs    # Check Python package version
```

### 2. Build and Run

```bash
cd examples/llm

# Create virtual environment
uv venv --seed -p 3.11

# Build the dataflow
dora build qwen-dev.yml --uv

# Run the dataflow
dora run qwen-dev.yml --uv
```

### 3. View the output

Connect Rerun viewer to see the conversation:

```bash
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

### 4. Interact

Simply speak into your microphone. The assistant will:
1. Detect when you start/stop speaking (VAD)
2. Transcribe your speech to text (Whisper)
3. Generate a response using Qwen LLM
4. Speak the response back to you (Kokoro TTS)

### 5. Stop the dataflow

```bash
dora stop
```

## Configuration

### Whisper Node

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_LANGUAGE` | Target language for transcription | `english` |

### TTS Node

| Variable | Description | Default |
|----------|-------------|---------|
| `ACTIVATION_WORDS` | Words that trigger TTS response | `you` |

## Dataflow Variants

- **qwen-dev.yml**: Standard voice assistant
- **qwen-dev-interruption.yml**: Voice assistant with interruption support (stops speaking when you start talking)

## Architecture

```
+------------+     +---------+     +------------------+
| microphone | --> |   VAD   | --> | distil-whisper   |
+------------+     +---------+     | (speech-to-text) |
                                   +------------------+
                                            |
                                            v
+------------+     +-------------+     +---------+
|  pyaudio   | <-- | kokoro-tts  | <-- |  qwen   |
| (speaker)  |     | (text-to-   |     |  (LLM)  |
+------------+     |   speech)   |     +---------+
                   +-------------+          |
                                            v
                                       +--------+
                                       |  plot  |
                                       | (rerun)|
                                       +--------+
```

## Troubleshooting

### Microphone Not Working

- Check microphone permissions in system settings
- Ensure the correct audio input device is selected
- Test microphone with other applications first

### No Audio Output

- Check speaker/headphone connections
- Verify audio output device settings
- Ensure portaudio is installed correctly

### Model Download

On first run, models (Whisper, Qwen, Kokoro) will be downloaded automatically. This may take time depending on your internet connection and model sizes.

### Version Mismatch Error

If you see errors like `invalid type: map, expected a YAML tag starting with '!'`:

```bash
# Check versions match
dora --version
pip show dora-rs

# Upgrade if needed
cargo install dora-cli --version X.Y.Z
pip install dora-rs==X.Y.Z
```

## Source Code

- [dora-microphone](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-microphone) - Microphone capture node
- [dora-vad](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-vad) - Voice Activity Detection node
- [dora-distil-whisper](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-distil-whisper) - Speech-to-Text node
- [dora-qwen](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-qwen) - Qwen LLM node
- [dora-kokoro-tts](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-kokoro-tts) - Text-to-Speech node
- [dora-pyaudio](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-pyaudio) - Audio playback node
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun) - Rerun visualization node
