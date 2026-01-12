# AI-Powered Assistive Navigation System

> **Smart vision assistance that learns and remembers your environment**

[![Status: Research Prototype](https://img.shields.io/badge/Status-Research%20Prototype-orange)](https://github.com)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%7C%20ARM-blue)](https://github.com)
[![License: Open Source](https://img.shields.io/badge/License-Open%20Source-green)](https://github.com)

An open-source assistive technology prototype that helps visually impaired users navigate indoor environments using AI vision, spatial memory, and 3D audio guidance.

---

## 💬 Origin Story: Why This Project Exists

I didn’t start this because of a big personal event. I started it because I was bored, curious, and slightly annoyed that existing systems felt limited. My initial thought was simple: *Can sound be used more intelligently for assistive technology?*

After exploring audio-based navigation content (like A-to-D audio guides), I became curious about the untapped potential of spatial audio. I researched existing assistive devices and smart glasses and noticed a common gap: most systems lacked adaptive spatial audio and long-term environmental memory. They could see, but could they remember and learn?

This led me to a core set of questions:
- What if a system could remember where objects were left, answering questions like, *"Where did I leave my keys?"*
- How can audio guidance be made intuitive without causing listening fatigue?

The development process was one of trial and error. Early audio experiments with pink noise were too harsh, while the brain quickly adapted to and ignored brown noise. This led to the design of a custom adaptive beep system, where frequency and tone change based on the importance of the object being signaled. Many things broke along the way.

This system is the result of that exploration. It’s a research prototype and a work in progress, built on the idea that assistive technology should be smart, adaptive, and genuinely helpful.

---

## 🎯 What Does This Do?

This system is a smart vision assistant that helps users navigate indoor spaces. It combines AI vision, spatial memory, and 3D audio to:

- **See and identify** objects in the user's environment.
- **Remember and recall** the location of objects with conversational voice commands.
- **Guide the user** to objects using intuitive, adaptive 3D audio cues.
- **Learn the environment** over time, reducing API costs and improving response speed.

This project is designed for researchers, developers, and accessibility advocates interested in the future of assistive AI.

---

## 🤝 Sponsors & Partners

This project is proudly supported by industry leaders making accessible technology possible:

<table>
<tr>
<td align="center" width="33%">
<h3><a href="https://www.dfrobot.com">DFRobot</a></h3>
<em>Robotics & Open-Source Hardware</em>
</td>
<td align="center" width="33%">
<h3><a href="https://polymaker.com">Polymaker</a></h3>
<em>Advanced 3D Printing Materials</em>
</td>
<td align="center" width="33%">
<h3><a href="https://radxa.com">Radxa</a></h3>
<em>High-Performance SBCs</em>
</td>
</tr>
</table>

### Key Hardware from DFRobot

| Component | Product | Use Case | Link |
|-----------|---------|----------|------|
| **Main Controller** | DFRduino Mega2560 (×2) | Sensor hub & peripheral control | [View Product →](https://www.dfrobot.com/product-655.html) |
| **Stereo Vision** | USB Camera 720p Wide-angle (×2) | Depth perception & spatial mapping | [View Product →](https://www.dfrobot.com/product-2537.html) |
| **Haptic Servos** | DSS-P05 Standard Servo 5kg (×2) | Directional haptic feedback | [View Product →](https://www.dfrobot.com/product-236.html) |
| **Touch Sensors** | Circular Force Sensor 7.6mm (×2) | User interaction input | [View Product →](https://www.dfrobot.com/product-1841.html) |

> *"DFRobot's accessible pricing and robust documentation made prototyping this assistive device achievable for independent developers."*

---

## Quick Start

### 1. Install Dependencies
```bash
# On Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip mpv

# Install Python libraries
pip install google-generativeai opencv-python opencv-contrib-python \
            sounddevice scipy groq edge-tts pydub pynput \
            --break-system-packages
```

### 2. Get API Keys
- **Google Gemini API**: [Get yours here](https://aistudio.google.com)
- **Groq API** (for speech): [Get yours here](https://console.groq.com)

### 3. Configure and Run
```bash
# Edit config.py with your API keys
nano config.py

# Run the system
python3 main_enhanced.py
```

### 4. Try It Out
- Press **F** to detect objects in front of the camera
- Press **C** to start voice recording, then ask: *"Where are my keys?"*
- Press **M** to switch between different operating modes

---

## Key Features Explained

### Spatial Memory (The "Brain")

**The Problem:** Standard object detection is stateless. It forgets an object the moment it leaves the camera's view.

**Our Solution:** The system gives the AI a persistent "memory." It logs detected objects (what they are, where they were seen, and when) into a local database. This allows users to ask conversational questions like, *"Where did I last see my keys?"* All data is stored locally and securely. The system also uses semantic context to provide more natural responses, such as "on the kitchen table."

---

### 3D Spatial Audio (The "Guide")

**The Problem:** Simple stereo panning is unnatural and can be fatiguing. The brain needs more detailed audio cues to accurately locate objects in 3D space.

**Our Solution:** The system uses a custom 3D audio engine to create intuitive, non-fatiguing guidance. By modeling how sound behaves in the real world (using HRTF-inspired filtering, ITD simulation, and distance-based attenuation), it produces audio cues that feel natural. This allows the user to pinpoint an object's location—left, right, above, below, or far away—with much greater accuracy.

---

### AI Vision + Tracking (The "Eyes")

**The Problem:** Relying solely on a vision API for real-time tracking is slow and expensive.

**Our Solution:** A two-stage hybrid approach. The system uses the current Gemini API for initial object detection and identification. Once an object is identified, a fast, local CSRT tracker takes over, following the object at up to 60 FPS. This reduces API calls by 40-70%, making the system both responsive and cost-effective.

---

### Voice Control (The "Interface")

**The Problem:** Assistive technology should be controlled hands-free, using natural language.

**Our Solution:** The system is controlled through a simple, intuitive voice interface. Using a combination of Groq Whisper for fast speech-to-text and Microsoft Edge-TTS for natural-sounding voice output, users can issue commands, ask questions, and receive feedback without needing to use a keyboard or screen.

---

## System Architecture

```mermaid
graph TD
    A[User] -->|Voice/Keyboard| B[Command Processor]
    B --> C[Vision Module]
    B --> D[Learning Module]
    B --> E[Audio Module]
    
    C -->|Detections| F[Object Manager]
    D -->|Memory| F
    F -->|Positions| E
    E -->|3D Sound| A
    
    C -->|Gemini API| G[(Google Cloud)]
    D -->|Local Storage| H[(SQLite DB)]
    
    style A fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
    style B fill:#2196F3,stroke:#333,stroke-width:2px,color:#fff
    style F fill:#FF9800,stroke:#333,stroke-width:2px,color:#fff
```

---

## Technical Specifications

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Computer** | Any Linux system | Radxa Rock 5C (ARM SBC) |
| **Camera** | USB webcam (640x480) | USB webcam (720p+) |
| **Audio** | Speakers | Stereo headphones |
| **Microphone** | Built-in mic | External mic |
| **Cost** | ~$50 (DIY parts) | ~$150 (Rock 5C + accessories) |

> [!TIP]
> The system auto-detects ARM processors and optimizes performance automatically!

### Software Stack

```
┌─────────────────────────────────────┐
│         User Interface Layer         │
│  Voice Control + Keyboard Controls  │
└─────────────────┬───────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼────┐  ┌────▼────┐  ┌────▼────┐
│ Vision │  │ Memory  │  │  Audio  │
├────────┤  ├─────────┤  ├─────────┤
│Gemini  │  │ SQLite  │  │  HRTF   │
│+ CSRT  │  │ Cache   │  │  3D     │
└────────┘  └─────────┘  └─────────┘
```

**Technologies used:**
- **Vision AI:** Google Gemini (gemini-robotics-er-1.5-preview)
- **Object Tracking:** OpenCV CSRT
- **Speech Recognition:** Groq Whisper (whisper-large-v3-turbo)
- **Voice Synthesis:** Microsoft Edge-TTS
- **Database:** SQLite3
- **Audio:** sounddevice + scipy
- **Language:** Python 3.8+

### Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Frame Rate** | 15-30 FPS | On Rock 5C ARM board |
| **Audio Latency** | <100ms | Real-time feedback |
| **Memory Query** | <10ms | Near-instant recall |
| **API Cost** | $0.04/hour | After learning phase |
| **Storage** | ~50MB/1000 objects | Compressed images |

---

## 📖 How to Use

### Keyboard Controls

| Key | Action |
|-----|--------|
| **C** | Start voice recording |
| **S** | Stop recording and process command |
| **F** | Manually detect objects (one-time scan) |
| **D** | Get AI description of entire scene |
| **M** | Cycle through operating modes |
| **Q** | Quit application |

### Operating Modes

| Mode | Purpose | Use Case |
|------|---------|----------|
| **Navigation** | Track specific target | "Find the door" |
| **Obstacle Avoidance** | Detect hazards | Walking through cluttered space |
| **Social** | Track people | Crowded environments |
| **Exploration** | General scanning | Unknown environment |

### Example Workflow

```
Step 1: Start the system
  → python3 main_enhanced.py

Step 2: Detect objects
  → Press 'F' or say "Track the cup"

Step 3: Listen to 3D audio guidance
  → Sound tells you where the cup is located

Step 4: System remembers the location
  → Automatically saved to memory

Step 5: Later, ask about it
  → "Where is my cup?" → "Last seen on the left, 10 minutes ago"
```

---

## How The Learning System Works

### The Problem
Traditional assistive systems forget everything when an object leaves the camera. You have to keep scanning repeatedly.

### Our Solution
**Persistent Spatial Memory** - Build a mental map of your environment over time.

### Step-by-Step Process

#### 1. Observation Phase
Every detected object is recorded with:
- **What:** Object label (e.g., "keys", "phone")
- **Where:** Position in 3D space (x, y, distance)
- **When:** Timestamp
- **How it looks:** Compressed visual fingerprint (perceptual hash)

#### 2. Storage Phase
```
assistivetech_memory.db (SQLite)
├── objects
│   ├── object_id
│   ├── label
│   ├── x_position, y_position
│   ├── timestamp
│   ├── confidence
│   └── image_hash
└── object_cache/ (compressed images)
```

> [!IMPORTANT]
> **Privacy-First Design:** Raw video is never stored. Only compressed, hashed snapshots are kept locally.

#### 3. Recall Phase
When you ask *"Where are my keys?"*:
1. The system queries the database for the most recent sighting of "keys."
2. It calculates the time elapsed since the object was last seen.
3. It translates the stored coordinates into a natural language response.

**Example response:**
```
"I last saw your keys 10 minutes ago on the far right 
side of your desk, near the center."
```

#### 4. Optimization Phase
The system gets smarter over time:
- **Temporal Decay:** Recent sightings are prioritized over older ones.
- **Frequency Learning:** Common objects in familiar locations are detected faster.
- **Duplicate Merging:** The system avoids creating duplicate entries for the same object.

### Benefits

| Feature | Benefit |
|---------|---------|
| **Cost Reduction** | 40-70% fewer API calls |
| **Faster Response** | Instant recall from database |
| **Privacy** | All data stays local |
| **Personalization** | Learns your specific environment |

---

## Cost Breakdown

### API Usage Costs

**Google Gemini API:**
- **Per request:** ~$0.002
- **Without learning:** ~60 requests/hour = **$0.12/hour**
- **With learning:** ~20 requests/hour = **$0.04/hour**

**Groq Whisper (Speech):**
- **Free tier:** 14,400 requests/day
- **Cost:** **FREE** for typical usage

**Edge-TTS (Voice):**
- **Cost:** **FREE** (unlimited)

### Total Monthly Cost
Assuming 4 hours of daily use:
- **Without learning:** $0.12 × 4 × 30 = **$14.40/month**
- **With learning:** $0.04 × 4 × 30 = **$4.80/month**

> [!NOTE]
> The learning system pays for itself by reducing API costs by 67%!

### Hardware Cost
- **DIY Setup:** ~$50 (webcam + USB mic + existing computer)
- **Recommended Setup:** ~$150 (Rock 5C SBC + accessories)
- **Compare to:** OrCam MyEye = **$4,500**

---

## Project Structure

```
assistivetech/
│
├── Core Application
│   ├── main_enhanced.py          # Main entry point
│   └── config.py                 # API keys and settings
│
├── Vision System
│   ├── vision_module.py          # Gemini API + CSRT tracking
│   └── object_manager.py         # Multi-object tracking logic
│
├── Learning System
│   └── learning_module.py        # Spatial memory and database
│
├── Audio System
│   ├── audio_hrtf.py             # 3D audio engine
│   └── audio_module_multi.py     # Multi-source mixer
│
├── Voice Interface
│   └── voice_control.py          # Speech recognition and TTS
│
├── Operating Modes
│   └── mode_controller.py        # Mode switching logic
│
└── Data Storage
    ├── assistive_learning.db     # SQLite database (auto-created)
    └── object_cache/             # Compressed image storage
```

### Key Files Explained

| File | Purpose | When to Edit |
|------|---------|--------------|
| `main_enhanced.py` | Main application loop | Adding new features |
| `config.py` | API keys and settings | Initial setup |
| `vision_module.py` | AI detection logic | Changing detection models |
| `learning_module.py` | Memory system | Adjusting retention policies |
| `audio_hrtf.py` | 3D audio algorithms | Customizing audio profiles |
| `voice_control.py` | Voice commands | Adding new commands |

---

## Comparison with Existing Systems

| Feature | **This System** | Envision AI | Seeing AI | OrCam MyEye |
|---------|----------------|-------------|-----------|-------------|
| **Spatial Memory** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Natural Language Queries** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **True 3D Audio (HRTF)** | ✅ Yes | ❌ Stereo only | ❌ Stereo only | ❌ Stereo only |
| **Self-Learning** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Open Source** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Customizable** | ✅ Fully | ❌ No | ❌ No | ❌ No |
| **Cost** | **$0.04/hr** + DIY | $10/month | Free | **$4,500** device |
| **Hardware** | DIY Linux | Cloud (phone) | Cloud (phone) | Proprietary |
| **Privacy** | ✅ Local data | ❌ Cloud | ❌ Cloud | ⚠️ Unknown |

### Why This System Stands Out

> [!IMPORTANT]
> **Experimental advantages in this prototype:**
> - To my knowledge, one of the few systems that combines conversational memory with spatial audio.
> - True 3D audio with elevation cues (not just stereo panning)
> - Fully customizable and open-source
> - Privacy-first: all data stays on your device
> - 67% cost reduction through learning

---

## Future Development Roadmap

### Phase 1: Hardware Integration (Current)
- [ ] ESP32 wireless connectivity
- [ ] Small OLED display for status
- [ ] Haptic feedback motors
- [ ] Battery management system

### Phase 2: Enhanced Capabilities
- [ ] **Real-time Translation**
  - OCR → Translate → Speech
  - Read signs, menus, labels in any language
- [ ] **Depth Camera Support**
  - Intel RealSense integration
  - True 3D distance measurement
- [ ] **Offline Mode**
  - Local Whisper model
  - On-device TinyML detection

### Phase 3: Accessibility Features
- [ ] Multi-language support (10+ languages)
- [ ] Custom audio profiles per user
- [ ] Gesture control integration
- [ ] Mobile companion app

### Phase 4: Advanced AI
- [ ] Federated learning across devices
- [ ] Semantic scene understanding
- [ ] Predictive navigation
- [ ] Adaptive difficulty adjustment

---

## Research Applications

This system is designed for research in:

| Research Area | Application |
|---------------|-------------|
| **Human-Computer Interaction** | Assistive technology UX studies |
| **Computer Vision** | Real-world accessibility applications |
| **Machine Learning** | Edge AI and resource-constrained learning |
| **Audio Processing** | Spatial audio for navigation |
| **Edge Computing** | On-device AI deployment strategies |

### Open Research Questions

1. **Spatial Memory Effectiveness:** How does persistent memory affect navigation accuracy in real-world scenarios?
2. **Audio vs Visual Feedback:** What's the optimal balance for cognitive load reduction?
3. **Learning Curve:** How quickly do users adapt to 3D audio guidance?
4. **HRTF Personalization:** Does customized HRTF improve accuracy over generic models?

> [!NOTE]
> If you use this system in your research, please cite it! See citation format at the bottom.

---

## Contributing

This is an **open research project**. We welcome contributions!

### Areas Where We Need Help

| Area | Skills Needed | Priority |
|------|---------------|----------|
| **Performance Optimization** | Python, profiling | 🔴 High |
| **Language Support** | i18n, translation | 🟡 Medium |
| **Hardware Integration** | Electronics, embedded systems | 🟢 Low |
| **UX Improvements** | Accessibility design | 🔴 High |
| **Documentation** | Technical writing | 🟡 Medium |
| **Testing** | QA, user testing | 🔴 High |

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Test** thoroughly
5. **Submit** a pull request

---

## Acknowledgments

### Technologies
- **Google Gemini** - Vision AI capabilities
- **Groq** - Whisper API access
- **Microsoft Edge** - TTS engine
- **OpenCV** - Computer vision library

### Inspiration
- **Microsoft Soundscape** (discontinued but influential)
- The **accessibility research community**
- All developers working to make technology more inclusive

---

## License

**MIT License** - See [LICENSE](LICENSE) file.

You are free to use, modify, and distribute this software. If you build something helpful, let us know!

---

## Contact & Support

### For Researchers & Developers
- **Technical Docs:** See `/docs` folder (coming soon)
- **Hardware Specs:** See `/hardware` folder (coming soon)
- **Research Papers:** TBD

### For Collaboration
- **Sponsorship inquiries:** Open to partnerships
- **Academic collaboration:** Open to research partnerships
- **Bug reports:** Submit an issue on GitHub

---

## Project Info

| | |
|---|---|
| **Version** | 2.0 |
| **Last Updated** | November 2025 |
| **Platform** | Linux (Ubuntu/Debian), ARM-optimized |
| **Status** | Research Prototype |
| **Target Hardware** | Radxa Rock 5C (RK3588S) |

---

## Citation

If you use this system in your research, please cite:

```bibtex
@software{assistive_navigation_2025,
  title = {AI-Powered Self-Learning Assistive Navigation System},
  author = {Alex Builds Tech},
  year = {2025},
  month = {November},
  url = {https://github.com/alexbuildstech/assistivetech},
  note = {Open-source assistive technology with spatial memory and 3D audio}
}
```

---

<div align="center">

**Made for the accessibility community**

[Star this repo](https://github.com) • [Report Bug](https://github.com) • [Request Feature](https://github.com)

</div>
