# Vision Language Model (VLM) Example

## Overview

This dataflow creates a vision-language interaction pipeline using Qwen2.5-VL:

```
Camera -> Qwen2.5-VL -> Rerun (Display)
```

The pipeline captures video from your camera, processes it with a Vision Language Model to understand and describe what it sees, and displays the results in the Rerun viewer. It can also integrate with speech for a complete multimodal experience.

## Nodes

- **opencv-video-capture**: Captures video from camera
- **dora-qwen2-5-vl**: Vision Language Model (Qwen2.5-VL) for image understanding
- **dora-qwenvl**: Original QwenVL model (alternative)
- **dora-rerun**: Visualizes camera feed and VLM responses
- **dora-microphone**: Captures audio for speech input (optional)
- **dora-vad**: Voice Activity Detection (optional)
- **dora-distil-whisper**: Speech-to-text for voice questions (optional)
- **dora-kokoro-tts**: Text-to-speech for spoken responses (optional)
- **dora-pyaudio**: Audio output for TTS (optional)

## Prerequisites

- Python 3.11+
- dora-rs
- Camera (webcam)
- uv (Python package manager)
- GPU recommended (CUDA/MPS for faster inference)

## Getting Started

### 1. Install dora

```bash
# Install dora CLI
cargo install dora-cli

# Or install Python package (must match CLI version)
pip install dora-rs
```

### 2. Build and Run

#### Vision-Only Mode (Simple)

```bash
cd examples/vlm

# Create virtual environment
uv venv --seed -p 3.11

# Build dataflow
dora build qwen2-5-vl-vision-only-dev.yml --uv

# Run dataflow
dora run qwen2-5-vl-vision-only-dev.yml --uv
```

#### Speech-to-Speech Mode (Full)

```bash
cd examples/vlm

# Create virtual environment
uv venv --seed -p 3.11

# Build dataflow
dora build qwenvl.yml --uv

# Run dataflow
dora run qwenvl.yml --uv
```

#### Without Cloning Repository

```bash
uv venv -p 3.11 --seed
dora build https://raw.githubusercontent.com/dora-rs/dora/main/examples/vlm/qwenvl.yml --uv
dora run https://raw.githubusercontent.com/dora-rs/dora/main/examples/vlm/qwenvl.yml --uv
```

### 3. View Results

```bash
# Connect to Rerun viewer
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

## Configuration

### Camera Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CAPTURE_PATH` | Camera device index or video path | `0` |
| `IMAGE_WIDTH` | Capture width | `640` |
| `IMAGE_HEIGHT` | Capture height | `480` |

### VLM Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DEFAULT_QUESTION` | Question to ask about the image | `Describe the image in three words.` |
| `IMAGE_RESIZE_RATIO` | Resize ratio for input images | `1.0` |
| `USE_MODELSCOPE_HUB` | Use ModelScope instead of HuggingFace | `false` |

### Whisper Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_LANGUAGE` | Language for speech recognition | `english` |

## Dataflow Variants

### Vision-Only
- `qwen2-5-vl-vision-only-dev.yml`: Camera + Qwen2.5-VL + Rerun (simple vision mode)

### Speech-to-Speech
- `qwenvl.yml`: Full pipeline with speech input/output using QwenVL + OuteTTS
- `qwen2-5-vl-speech-to-speech-dev.yml`: Full pipeline with Qwen2.5-VL + Kokoro TTS
- `qwenvl-dev.yml`: Development version with local node paths

## Architecture

### Vision-Only Pipeline

```
+--------+     +-------------+     +--------+
| Camera | --> | Qwen2.5-VL  | --> | Rerun  |
+--------+     | (VLM)       |     |(Display)|
               +-------------+     +--------+
```

### Speech-to-Speech Pipeline

```
+------------+     +---------+     +---------+
| Microphone | --> |   VAD   | --> | Whisper |
+------------+     +---------+     | (STT)   |
                                   +---------+
                                        |
                                        v
+--------+     +-------------+     +---------+     +--------+
| Camera | --> | Qwen2.5-VL  | <-- | Question|     | Rerun  |
+--------+     | (VLM)       |     +---------+     |(Display)|
               +-------------+                     +--------+
                    |                                  ^
                    v                                  |
               +---------+     +---------+             |
               | Kokoro  | --> | PyAudio |-------------+
               | (TTS)   |     |(Speaker)|
               +---------+     +---------+
```

## Features

- **Real-time Vision Understanding**: Describe scenes, identify objects, read text
- **Voice Interaction**: Ask questions about what the camera sees using voice
- **Spoken Responses**: Hear the VLM's answers through text-to-speech
- **Customizable Prompts**: Configure default questions for automated analysis
- **Multi-model Support**: Choose between Qwen2.5-VL or original QwenVL

## Use Cases

- **Accessibility**: Describe surroundings for visually impaired users
- **Quality Inspection**: Automated visual inspection with voice feedback
- **Interactive Demos**: Voice-controlled image analysis
- **Robotics**: Visual understanding for autonomous systems
- **Education**: Interactive learning about visual content

## Troubleshooting

### Camera Issues
- Check system camera permissions
- Verify correct camera device index in `CAPTURE_PATH`
- Test camera in other applications first

### Model Download Slow
- First run downloads VLM models which may be several GB
- Ensure stable internet connection
- Models are cached after first download
- Use `USE_MODELSCOPE_HUB=true` for faster downloads in China

### GPU Memory Issues
- Qwen2.5-VL requires significant GPU memory
- Reduce `IMAGE_RESIZE_RATIO` for lower memory usage
- Use smaller model variants if available

### Microphone Issues (Speech-to-Speech)
- Check system microphone permissions
- Verify correct audio input device is selected
- Test microphone in other applications first

### Rerun Version Mismatch
- If you see version warnings, install matching Rerun SDK:
  ```bash
  pip install rerun-sdk==<version>
  ```

## Source Code

- [opencv-video-capture](https://github.com/dora-rs/dora-hub/tree/main/node-hub/opencv-video-capture)
- [dora-qwen2-5-vl](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-qwen2-5-vl)
- [dora-qwenvl](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-qwenvl)
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun)
- [dora-distil-whisper](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-distil-whisper)
- [Qwen2.5-VL (Alibaba)](https://github.com/QwenLM/Qwen2.5-VL)
