# 🧭 AI-Powered Assistive Navigation System
## 🤝 Sponsors & Partners


This project is proudly supported by industry leaders making accessible technology possible:


<table>
<tr>
<td align="center" width="33%">
<h3><a href="https://www.dfrobot.com">🤖 DFRobot</a></h3>
<em>Robotics & Open-Source Hardware</em>
</td>
<td align="center" width="33%">
<h3><a href="https://polymaker.com">🎨 Polymaker</a></h3>
<em>Advanced 3D Printing Materials</em>
</td>
<td align="center" width="33%">
<h3><a href="https://radxa.com">💻 Radxa</a></h3>
<em>High-Performance SBCs</em>
</td>
</tr>
</table>


### 🔧 Key Hardware from DFRobot


| Component | Product | Use Case | Link |
|-----------|---------|----------|------|
| **Main Controller** | DFRduino Mega2560 (×2) | Sensor hub & peripheral control | [View Product →](https://www.dfrobot.com/product-191.html) |
| **Stereo Vision** | USB Camera 720p Wide-angle (×2) | Depth perception & spatial mapping | [View Product →](https://www.dfrobot.com/product-2089.html) |
| **Haptic Servos** | DSS-P05 Standard Servo 5kg (×2) | Directional haptic feedback | [View Product →](https://www.dfrobot.com/product-188.html) |
| **Touch Sensors** | Circular Force Sensor 7.6mm (×2) | User interaction input | [View Product →](https://www.dfrobot.com/product-2058.html) |


> 💬 *"DFRobot's accessible pricing and robust documentation made prototyping this assistive device achievable for independent developers."*


---


## ⚡ Quick Start


### 1️⃣ Install Dependencies
```bash
# On Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip mpv


# Install Python libraries
pip install google-generativeai opencv-python opencv-contrib-python \
            sounddevice scipy groq edge-tts pydub pynput \
            --break-system-packages
```


### 2️⃣ Get API Keys
- **Google Gemini API**: [Get yours here](https://aistudio.google.com)
- **Groq API** (for speech): [Get yours here](https://console.groq.com)


### 3️⃣ Configure and Run
