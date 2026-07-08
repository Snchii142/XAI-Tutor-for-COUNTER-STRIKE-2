# 🎯 APEX — Adaptive Player Experience Coach for CS2

> A real-time AI coaching overlay for Counter-Strike 2.  
> Uses **YOLOv8** (enemy detection) + **XGBoost** (combat prediction) + **Groq LLM** (buy recommendations) to coach you mid-game — like having a pro IGL in your ear.

---

## 🖥️ System Requirements

- **OS:** Windows 10 / 11 (64-bit) — macOS/Linux NOT supported
- **Python:** 3.10 or 3.11
- **GPU:** Optional but recommended (NVIDIA for faster YOLO inference)
- **CS2:** Must be installed via Steam
- **RAM:** 8GB minimum

---

## 📦 Step 1 — Download & Setup

### 1.1 Clone the repo
```bash
git clone https://github.com/Snchii142/XAI-Tutor-for-COUNTER-STRIKE-2.git
cd XAI-Tutor-for-COUNTER-STRIKE-2
```

### 1.2 Download the XGBoost model (required)
The combat prediction model is hosted separately due to file size.

👉 **[Download best_overall_model.pkl from Google Drive](https://drive.google.com/file/d/1Lvjv-_sNz65XiJzXypPCCAltz3NkZI59/view?usp=drive_link)**

After downloading, place it here:
```
XAI-Tutor-for-COUNTER-STRIKE-2/
    └── results/
            └── best_overall_model.pkl   ← put it here
```

> ⚠️ Create the `results` folder manually if it doesn't exist.

### 1.3 Install Python dependencies
```bash
pip install -r req.txt
```

---

## 🔑 Step 2 — Get Your Groq API Key (Free)

APEX uses Groq LLM for real-time buy recommendations. It's completely free.

1. Go to **[https://console.groq.com](https://console.groq.com)**
2. Sign up / Log in
3. Click **"API Keys"** → **"Create API Key"**
4. Copy the key

Now create a `.env` file in the project folder:
```bash
copy .env.example .env
```
Open `.env` and paste your key:
```
GROQ_API_KEY=your_actual_key_here
```

---

## ⚙️ Step 3 — CS2 GSI Config (Very Important!)

APEX reads your live game state via CS2's built-in Game State Integration. You need to add one config file to CS2.

### 3.1 Find your CS2 cfg folder
Open File Explorer and navigate to:
```
C:\Program Files (x86)\Steam\userdata\<YOUR_STEAM_ID>\730\local\cfg\
```
> 💡 Don't know your Steam ID? Open Steam → click your profile name (top right) → "Account Details" — the number shown is your Steam ID.

### 3.2 Create the config file
Inside that `cfg` folder, create a new file named:
```
gamestate_integration_apex.cfg
```

Paste this inside it:
```
"APEX GSI"
{
    "uri" "http://127.0.0.1:3000"
    "timeout" "5.0"
    "heartbeat" "10.0"
    "data"
    {
        "provider"              "1"
        "map"                   "1"
        "round"                 "1"
        "player_id"             "1"
        "player_state"          "1"
        "player_weapons"        "1"
        "player_match_stats"    "1"
    }
}
```
Save the file.

### 3.3 Verify CS2 launch options (optional but recommended)
In Steam → Right click CS2 → Properties → Launch Options, add:
```
-gamestateintegration
```

---

## 🚀 Step 4 — Run APEX

1. **Launch CS2 first**
2. Open a terminal in the project folder and run:
```bash
python coach.py
```
3. The APEX overlay will appear in the **top-left corner** of your screen
4. Jump into a match!

---

## 🎮 How It Works

| Feature | What it does |
|--------|--------------|
| 👁️ **Enemy Detection** | YOLOv8 scans your screen in real-time to detect enemies |
| ⚡ **Combat Prediction** | XGBoost model tells you: `OPTIMAL ENGAGEMENT - FIRE!` or `HOLD - BAD ENGAGE` |
| 💰 **Buy Recommendations** | Groq LLM analyzes enemy economy + your money and suggests what to buy each round |
| 🔊 **Voice Coaching** | All tips are spoken aloud via text-to-speech |
| ⌨️ **Hotkey** | Press `Alt + M` to minimize/show the overlay |

---

## 🛠️ Troubleshooting

**Overlay not showing?**
→ Run `python coach.py` as Administrator (right click → Run as admin)

**`ModuleNotFoundError`?**
→ Run `pip install -r req.txt` again

**LLM shows "GROQ offline"?**
→ Check your `.env` file — make sure `GROQ_API_KEY` is set correctly

**Enemy not being detected?**
→ Make sure CS2 is running in **Windowed Fullscreen** mode, not exclusive fullscreen

**Wrong screen resolution?**
→ Open `apex_config.json` and set your actual resolution:
```json
{
    "screen_width": 1920,
    "screen_height": 1080,
    "aspect_ratio": "16:9",
    "distance_constant": 66440
}
```

---

## 📁 Project Structure

```
XAI-Tutor-for-COUNTER-STRIKE-2/
├── coach.py                  # Main application
├── config.py                 # Screen resolution config
├── best.onnx                 # YOLOv8 enemy detection model
├── apex_live.gif             # Overlay animation
├── apex_config.json          # Resolution settings
├── req.txt                   # Python dependencies
├── .env.example              # API key template
└── results/
    └── best_overall_model.pkl  # XGBoost combat model (download separately)
```

---

## 📊 Model Info

- **YOLOv8** (`best.onnx`) — Custom trained on CS2 gameplay footage for T/CT detection
- **XGBoost** (`best_overall_model.pkl`) — Trained on 17 combat features including crosshair distance, health, armor, weapon class, movement state, and enemy position
- **Groq LLM** (`llama-3.1-8b-instant`) — Real-time buy strategy via API

---

## ⚠️ Disclaimer

This tool is intended for **educational and research purposes only**.  
It does not inject into the game, modify memory, or violate VAC.  
It only reads screen pixels and CS2's official GSI output.

---

## 🙋 Issues?

Open a GitHub issue or reach out. Happy fragging! 💚
