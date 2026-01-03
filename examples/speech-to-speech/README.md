# Speech-to-Speech Example

This example demonstrates a real-time speech-to-speech pipeline using dora-rs. It captures your voice, transcribes it using Whisper, and speaks the transcription back using Kokoro TTS.

## Overview

The dataflow creates a complete speech echo pipeline:

```
microphone -> VAD -> Whisper (STT) -> Kokoro (TTS) -> speaker
                                           |
                                           v
                                       rerun (display)
```

### Nodes

- **dora-microphone**: Captures audio from your microphone
- **dora-vad**: Voice Activity Detection - detects when you're speaking
- **dora-distil-whisper**: Speech-to-Text using Distil-Whisper model
- **dora-kokoro-tts**: Text-to-Speech using Kokoro for voice output
- **dora-pyaudio**: Plays audio through your speakers
- **dora-rerun**: Visualizes transcription in Rerun viewer

## Prerequisites

- Python 3.11+
- dora-rs
- Microphone and speakers
- portaudio and espeak-ng installed

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
cd examples/speech-to-speech

# Create virtual environment
uv venv --seed -p 3.11

# Build the dataflow
dora build kokoro-dev.yml --uv

# Run the dataflow
dora run kokoro-dev.yml --uv
```

### 3. View the output

Connect Rerun viewer to see the transcription:

```bash
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

### 4. Interact

Simply speak into your microphone. The pipeline will:
1. Detect when you start/stop speaking (VAD)
2. Transcribe your speech to text (Whisper)
3. Speak the transcription back to you (Kokoro TTS)

### 5. Stop the dataflow

```bash
dora stop
```

## Configuration

### Whisper Node

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_LANGUAGE` | Target language for transcription | `english` |

## Dataflow Variants

- **kokoro-dev.yml**: Uses Kokoro TTS for voice synthesis
- **outtetts-dev.yml**: Uses OuteTTS for voice synthesis
- **outtetts.yml**: Production version with OuteTTS

## Architecture

```
+------------+     +---------+     +------------------+
| microphone | --> |   VAD   | --> | distil-whisper   |
+------------+     +---------+     | (speech-to-text) |
                                   +------------------+
                                            |
                                            v
+------------+     +-------------+     +---------+
|  pyaudio   | <-- | kokoro-tts  | <-- | whisper |
| (speaker)  |     | (text-to-   |     |  (STT)  |
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

### PyAudio Architecture Mismatch (macOS Apple Silicon)

If you see errors like `incompatible architecture (have 'x86_64', need 'arm64')`:

```bash
# Remove old pyaudio and reinstall with correct architecture
pip uninstall pyaudio
ARCHFLAGS="-arch arm64" pip install --no-cache-dir --no-binary :all: pyaudio
```

### Model Download

On first run, models (Whisper, Kokoro) will be downloaded automatically. This may take time depending on your internet connection and model sizes.

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
- [dora-kokoro-tts](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-kokoro-tts) - Text-to-Speech node
- [dora-pyaudio](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-pyaudio) - Audio playback node
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun) - Rerun visualization node
