# Translation Example

## Overview

This dataflow creates a real-time speech translation pipeline:

```
Microphone -> VAD -> Whisper (STT) -> Translation -> Rerun (Display)
```

The pipeline captures audio from your microphone, detects speech activity, transcribes your speech using Whisper, translates it to another language, and displays the results in the Rerun viewer.

## Nodes

- **dora-microphone**: Captures audio from microphone
- **dora-vad**: Voice Activity Detection - detects when you're speaking
- **dora-distil-whisper**: Speech-to-text using Distil-Whisper model
- **dora-argotranslate**: Offline translation using Argos Translate
- **dora-phi4**: Multimodal translation using Microsoft Phi-4 (alternative)
- **dora-rerun**: Visualizes transcription and translation in Rerun viewer
- **dora-kokoro-tts**: Text-to-speech for translated output (optional)
- **dora-pyaudio**: Audio output for TTS (optional)

## Prerequisites

- Python 3.11+
- dora-rs
- Microphone
- uv (Python package manager)
- GPU recommended for Phi-4 (CUDA required for flash-attn)

## Getting Started

### 1. Install dora

```bash
# Install dora CLI
cargo install dora-cli

# Or install Python package (must match CLI version)
pip install dora-rs
```

### 2. Build and Run

#### Using Phi-4 (Multimodal Translation)

```bash
cd examples/translation

# Create virtual environment
uv venv --seed -p 3.11

# Build dataflow
dora build phi4-dev.yml --uv

# Run dataflow
dora run phi4-dev.yml --uv

# Start talking in English, Chinese, German, French, Italian, Japanese, Spanish, or Portuguese
```

#### Using Argos Translate (Offline Translation)

```bash
cd examples/translation

# Create virtual environment
uv venv --seed -p 3.11

# Build English to Chinese translation
dora build dataflow_en_zh.yml --uv

# Run dataflow
dora run dataflow_en_zh.yml --uv
```

### 3. View Results

```bash
# Connect to Rerun viewer
rerun --connect rerun+http://127.0.0.1:9876/proxy
```

## Configuration

### Whisper Node Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TARGET_LANGUAGE` | Language of spoken input | `english` |
| `TRANSLATE` | Enable Whisper translation | `false` |

### Argos Translate Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SOURCE_LANGUAGE` | Source language code (e.g., en, zh, fr) | Required |
| `TARGET_LANGUAGE` | Target language code (e.g., en, zh, fr) | Required |

### Phi-4 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LEAD_MODALITY` | Primary input modality | `audio` |

## Dataflow Variants

### Argos Translate Pipelines
- `dataflow_en_zh.yml`: English to Chinese
- `dataflow_zh_en.yml`: Chinese to English
- `dataflow_en_fr.yml`: English to French
- `dataflow_fr_en.yml`: French to English
- `dataflow_en_zh_terminal.yml`: English to Chinese (terminal output)
- `dataflow_zh_en_terminal.yml`: Chinese to English (terminal output)
- `dataflow_en_zh_terminal_argo.yml`: English to Chinese with terminal display

### Phi-4 Pipeline
- `phi4-dev.yml`: Multimodal translation with TTS output (supports 8+ languages)

## Architecture

### Argos Translate Pipeline

```
+------------+     +---------+     +------------------+     +------------------+
| Microphone | --> |   VAD   | --> | distil-whisper   | --> | argos-translate  |
+------------+     +---------+     | (Speech-to-Text) |     | (Translation)    |
                                   +------------------+     +------------------+
                                                                    |
                                                                    v
                                                               +--------+
                                                               | rerun  |
                                                               |(Display)|
                                                               +--------+
```

### Phi-4 Pipeline (with TTS)

```
+------------+     +---------+     +------------------+     +------------------+
| Microphone | --> |   VAD   | --> |     Phi-4        | --> |   kokoro-tts     |
+------------+     +---------+     | (Multimodal AI)  |     | (Text-to-Speech) |
                                   +------------------+     +------------------+
                                            |                        |
                                            v                        v
                                       +--------+              +-----------+
                                       | rerun  |              | pyaudio   |
                                       |(Display)|             | (Speaker) |
                                       +--------+              +-----------+
```

## Supported Languages

### Argos Translate
- English (en)
- Chinese (zh)
- French (fr)
- German (de)
- Spanish (es)
- Italian (it)
- Portuguese (pt)
- And many more...

### Phi-4 Multimodal
- English
- Chinese
- German
- French
- Italian
- Japanese
- Spanish
- Portuguese

## Troubleshooting

### Microphone Issues
- Check system microphone permissions
- Verify correct audio input device is selected
- Test microphone in other applications first

### Model Download Slow
- First run downloads Whisper and translation models which may take time
- Ensure stable internet connection
- Models are cached after first download

### Phi-4 Flash Attention Error
- flash-attn requires CUDA and Linux
- Install with: `pip install flash-attn --no-build-isolation`
- For non-CUDA systems, use Argos Translate pipelines instead

### Argos Language Package Not Found
- Install language packages: `argospm install translate-en_zh`
- Check available packages: `argospm search`

### Rerun Version Mismatch
- If you see version warnings, install matching Rerun SDK:
  ```bash
  pip install rerun-sdk==<version>
  ```

## Source Code

- [dora-microphone](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-microphone)
- [dora-vad](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-vad)
- [dora-distil-whisper](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-distil-whisper)
- [dora-argotranslate](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-argotranslate)
- [dora-rerun](https://github.com/dora-rs/dora-hub/tree/main/node-hub/dora-rerun)
- [Argos Translate](https://github.com/argosopentech/argos-translate)
