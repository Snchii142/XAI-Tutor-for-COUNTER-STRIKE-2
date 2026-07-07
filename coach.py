import dxcam
import time
import json
import pickle
import numpy as np
import pandas as pd
import xgboost as xgb
from ultralytics import YOLO
import threading
import queue
import customtkinter as ctk
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import pyttsx3
import os
import traceback
import logging
from groq import Groq
from dotenv import load_dotenv
from PIL import Image
from config import SCREEN_WIDTH, SCREEN_HEIGHT, CX, CY, DEG_PER_PIX_X, DEG_PER_PIX_Y, DISTANCE_CONSTANT
import pythoncom
import keyboard

# ==========================================
# 0. LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler("apex_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("Apex")

# ==========================================
# 1. GLOBALS & API
# ==========================================
CURRENT_GSI = {
    "round_phase": "unknown", "health": 100, "armor": 100, "weapon": "rifle", "ammo": 30,
    "money": 800, "enemy_score": 0, "enemy_loss_bonus": 0, "team": "T",
    "ducking": 0, "scoped": 0, "is_moving": 0, "is_reloading": 0
}
MODEL_FEATURES = [
    "health_player",
    "armor_value_player",
    "m_iClip1_player",
    "ducking_player",
    "scoped_player",
    "is_moving",
    "is_reloading",
    "distance_3d",
    "delta_yaw",
    "delta_pitch",
    "crosshair_distance",
    "enemy_on_screen",
    "class_sniper",
    "class_rifle",
    "class_smg",
    "class_pistol",
    "class_heavy"
]
state_lock = threading.Lock()
COMBAT_HISTORY = deque(maxlen=128)

tts_queue = queue.Queue()

load_dotenv()
try:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env")
    groq_client = Groq(api_key=api_key)
    GROQ_AVAILABLE = True
    log.info("Groq client initialized successfully.")
except Exception as e:
    log.error(f"Groq LLM offline: {e}")
    GROQ_AVAILABLE = False

# ==========================================
# 2. DEDICATED TTS THREAD
# ==========================================
def tts_worker():
    pythoncom.CoInitialize()
    while True:
        text = tts_queue.get()          
        if text is None:                
            break
        engine = None
        try:
            text = str(text).strip()
            if not text:
                continue

            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            engine.setProperty('volume', 1.0)

            voices = engine.getProperty('voices')
            female_voice = next((
                v for v in voices
                if 'female' in v.name.lower()
                or 'zira' in v.name.lower()
                or 'hazel' in v.name.lower()
                or 'susan' in v.name.lower()
            ), None)
            if female_voice:
                engine.setProperty('voice', female_voice.id)

            engine.say(text)
            engine.runAndWait()
            log.debug(f"TTS spoke: {text[:60]}")
        except Exception as e:
            log.error(f"TTS speak error: {type(e).__name__}: {e}")
        finally:
            if engine:
                try:
                    engine.stop()
                except Exception:
                    pass

    pythoncom.CoUninitialize()

def speak(text):
    tts_queue.put(text)

# ==========================================
# 3. GAMING OVERLAY (CustomTkinter + Live Icon)
# ==========================================
class AnimatedIcon:
    def __init__(self, label, gif_path, size=(30, 30), speed=50):
        self.label = label
        self.speed = speed
        self.frames = []

        try:
            gif = Image.open(gif_path)
            while True:
                frame_image = ctk.CTkImage(light_image=gif.copy().convert("RGBA"), size=size)
                self.frames.append(frame_image)
                gif.seek(len(self.frames))
        except EOFError:
            pass
        except Exception as e:
            log.warning(f"Could not load live icon: {e}")

        self.frame_index = 0
        if self.frames:
            self.animate()

    def animate(self):
        self.label.configure(image=self.frames[self.frame_index])
        self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.label.after(self.speed, self.animate)


class ApexOverlay:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("Apex - Adaptive Player Experience Coach")

        self.current_x = 20
        self.is_minimized = False
        self._is_sliding = False

        self.root.geometry(f"460x160+{self.current_x}+20")
        self.root.overrideredirect(True)
        self.root.attributes("-alpha", 0.9)
        self.root.attributes("-topmost", True)

        self.main_frame = ctk.CTkFrame(
            self.root,
            corner_radius=15,
            fg_color="#111111",
            border_width=2,
            border_color="#00ffcc"
        )
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=0)

        self.left_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.left_container.grid(row=0, column=0, sticky="nsew", padx=(15, 10), pady=15)

        self.lbl_icon = ctk.CTkLabel(
            self.left_container,
            text="COACH APEX (Alt+M)",
            font=("Consolas", 16, "bold"),
            text_color="#00ffcc"
        )
        self.lbl_icon.pack(anchor="w")

        self.lbl_msg = ctk.CTkLabel(
            self.left_container,
            text="Initializing...",
            font=("Consolas", 12),
            text_color="#ffffff",
            justify="left",
            wraplength=250
        )
        self.lbl_msg.pack(anchor="w", pady=(15, 0))

        self.lbl_eco = ctk.CTkLabel(
            self.left_container,
            text="System: Standby",
            font=("Consolas", 10, "bold"),
            text_color="#555555"
        )
        self.lbl_eco.pack(anchor="sw", side="bottom")

        self.right_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.right_container.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)

        self.lbl_gif = ctk.CTkLabel(self.right_container, text="")
        self.lbl_gif.pack(expand=True)

        if os.path.exists("apex_live.gif"):
            self.animator = AnimatedIcon(self.lbl_gif, "apex_live.gif", size=(80, 80), speed=60)

        keyboard.on_press_key("m", self.handle_hotkey)

    def update_text(self, msg, eco_text=""):
        self.root.after(0, self._apply_update, msg, eco_text)

    def _apply_update(self, msg, eco_text):
        self.lbl_msg.configure(text=msg)
        if eco_text:
            self.lbl_eco.configure(text=eco_text)

    def update_eco(self, eco_text):
        self.root.after(0, self._apply_eco, eco_text)

    def _apply_eco(self, eco_text):
        if eco_text:
            self.lbl_eco.configure(text=eco_text)

    def handle_hotkey(self, event):
        if keyboard.is_pressed("alt"):
            self.toggle_slide()

    def toggle_slide(self, event=None):
        if self._is_sliding:
            return
        self.is_minimized = not self.is_minimized
        target_x = -440 if self.is_minimized else 20
        self.animate_slide(target_x)

    def animate_slide(self, target_x):
        self._is_sliding = True
        step = 40 if target_x > self.current_x else -40
        
        def step_animation():
            if (step > 0 and self.current_x >= target_x) or (step < 0 and self.current_x <= target_x):
                self.current_x = target_x
                self.root.geometry(f"460x160+{self.current_x}+20")
                self._is_sliding = False
            else:
                self.current_x += step
                self.root.geometry(f"460x160+{self.current_x}+20")
                self.root.after(10, step_animation)
                
        step_animation()

def boot_sequence(overlay):
    steps = [
        ("Hi! I am your coach, Apex - Adaptive Player Experience Coach.", "#00ffcc"),
        ("Setting things up...", "#ffffff"),
        ("Let's open the game.", "#00ffcc")
    ]
    for msg, color in steps:
        overlay.root.after(0, lambda m=msg, c=color: overlay.lbl_msg.configure(text=m, text_color=c))
        speak(msg)
        time.sleep(2)

# ==========================================
# 4. GSI & DATA LOGIC 
# ==========================================
class CS2StateParser:
    def __init__(self, raw_data): self.raw = raw_data
    def parse(self):
        try:
            map_data = self.raw.get('map', {})
            player = self.raw.get('player', {})
            state = player.get('state', {})
            weapons = player.get('weapons', {})

            player_team = player.get('team', 'T') 
            enemy_team_key = 'team_t' if player_team == 'CT' else 'team_ct'
            enemy_data = map_data.get(enemy_team_key, {})

            active_weapon, ammo = "none", 0
            is_reloading = 0
            scoped = 0
            for k, w in weapons.items():
                if w.get('state') == 'active':
                    active_weapon = w.get('name', 'unknown').replace("weapon_", "")
                    ammo = w.get('ammo_clip', 0)
                    is_reloading = 1 if w.get('state') == 'reloading' else 0
                    zoom_level = w.get('zoom_level', 0)
                    scoped = 1 if isinstance(zoom_level, (int, float)) and zoom_level > 0 else 0

            ducking = 1 if state.get('ducking', 0) else 0
            velocity = state.get('velocity', state.get('speed', 0))
            if isinstance(velocity, dict):
                vx = float(velocity.get('x', 0))
                vy = float(velocity.get('y', 0))
                vz = float(velocity.get('z', 0))
                speed = (vx * vx + vy * vy + vz * vz) ** 0.5
            elif isinstance(velocity, (list, tuple)):
                vx = float(velocity[0]) if len(velocity) > 0 else 0.0
                vy = float(velocity[1]) if len(velocity) > 1 else 0.0
                vz = float(velocity[2]) if len(velocity) > 2 else 0.0
                speed = (vx * vx + vy * vy + vz * vz) ** 0.5
            else:
                speed = float(velocity or 0)
            is_moving = 1 if speed > 5.0 else 0

            return {
                "round_phase": self.raw.get('round', {}).get('phase', 'unknown'),
                "health": state.get('health', 0),
                "armor": state.get('armor', 0),
                "weapon": active_weapon,
                "ammo": ammo,
                "money": state.get('money', 0),
                "enemy_score": enemy_data.get('score', 0),
                "enemy_loss_bonus": enemy_data.get('consecutive_round_losses', 0),
                "team": player_team,
                "ducking": ducking,
                "scoped": scoped,
                "is_moving": is_moving,
                "is_reloading": is_reloading
            }
        except Exception as e:
            log.error(f"GSI parse error: {e}")
            return {}

class GSIServer(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            new_state = CS2StateParser(data).parse()
            if new_state:
                with state_lock:
                    CURRENT_GSI.update(new_state)
            self.send_response(200)
            self.end_headers()
        except Exception as e:
            log.error(f"GSI server handler error: {e}")
    def log_message(self, format, *args): pass

class EnemyEconomyTracker:
    def __init__(self):
        self.bank = 800
        self.last_score = 0
    def update(self, enemy_score, loss_bonus_count):
        loss_bonus = min(1400 + (loss_bonus_count * 500), 3400)
        if enemy_score > self.last_score: self.bank += 3250
        else: self.bank += loss_bonus
        self.last_score = enemy_score

        if self.bank > 4500:
            status = "FULL BUY"
            self.bank -= 4100
        elif self.bank > 2000:
            status = "FORCE BUY"
            self.bank -= 1500
        else:
            status = "ECO ROUND"
        return f"TARGET ECON: ~${self.bank} ({status})"

class OpponentMemoryMatrix:
    def __init__(self): self.history = []
    def log_round(self, round_num, strat): self.history.append(f"R{round_num}: {strat}")
    def get_context(self): return " | ".join(self.history[-3:])

def map_weapon_class(weapon_name):
    return {
        'class_sniper': 1 if weapon_name in ['awp', 'ssg08'] else 0,
        'class_rifle': 1 if weapon_name in ['ak47', 'm4a1', 'm4a1_silencer'] else 0,
        'class_smg': 1 if weapon_name in ['mac10', 'mp9', 'ump45'] else 0,
        'class_pistol': 1 if weapon_name in ['glock', 'usp_silencer', 'deagle'] else 0,
        'class_heavy': 0
    }

def is_enemy_label(class_name, player_team):
    if not player_team:
        return False
    label = class_name.upper().replace(" ", "").replace("_", "").replace("-", "")
    if player_team == 'CT':
        enemy_labels = {'T', 'TERRORIST', 'TERRORISTS', 'TERROR', '0'}
    elif player_team == 'T':
        enemy_labels = {'CT', 'COUNTERTERRORIST', 'COUNTERTERRORISTS', 'COUNTER', '1'}
    else:
        return False
    return label in enemy_labels

# ==========================================
# 5. BACKGROUND ENGINES
# ==========================================
def run_vision_engine(overlay, camera):
    log.info("Vision engine starting...")
    try:
        vision_model = YOLO('best.onnx', task='detect')
        with open('results/best_overall_model.pkl', 'rb') as f:
            combat_model = pickle.load(f)
        camera.start(target_fps=64)
        log.info("Vision engine ready.")
    except Exception as e:
        log.critical(f"Vision engine failed to initialize: {e}\n{traceback.format_exc()}")
        return

    last_health = 100
    last_engage_time = 0
    last_enemy_seen = 0
    last_display_text = None
    last_prediction = None
    ENGAGE_COOLDOWN = 2.0  
    NO_ENEMY_GRACE = 0.6
    DEFAULT_OVERLAY_TEXT = "No enemy detected."

    overlay.update_text(DEFAULT_OVERLAY_TEXT)
    last_display_text = DEFAULT_OVERLAY_TEXT

    while True:
        try:
            frame = camera.get_latest_frame()
            if frame is None:
                continue

            results = vision_model(frame, verbose=False)[0]
            with state_lock:
                gsi = CURRENT_GSI.copy()

            if gsi['health'] == 0 and last_health > 0:
                if len(COMBAT_HISTORY) > 30:
                    avg_dist = np.mean([t['cross_dist'] for t in list(COMBAT_HISTORY)[-64:]])
                    msg = "Lazy crosshair placement. You flicked too far." if avg_dist > 5.0 else "Good geometry. Unlucky aim duel."
                    overlay.update_text(f"DEATH LOG: {msg}")
            last_health = gsi['health']

            enemy_detected = False

            if len(results.boxes) > 0 and gsi['health'] > 0:
                player_team = gsi.get('team', 'T')
                
                valid_enemy_box = None
                min_cross_dist = float('inf')

                for r_box in results.boxes:
                    cls_id = int(r_box.cls[0].item())
                    class_name = results.names[cls_id]

                    if is_enemy_label(class_name, player_team):
                        box = r_box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = box
                        d_yaw = (((x1 + x2) / 2) - CX) * DEG_PER_PIX_X
                        d_pitch = (((y1 + y2) / 2) - CY) * DEG_PER_PIX_Y
                        dist = np.sqrt(d_yaw**2 + d_pitch**2)
                        
                        if dist < min_cross_dist:
                            min_cross_dist = dist
                            valid_enemy_box = box

                if valid_enemy_box is not None:
                    x1, y1, x2, y2 = valid_enemy_box

                    last_enemy_seen = time.time()
                    enemy_detected = True

                    d_yaw = (((x1 + x2) / 2) - CX) * DEG_PER_PIX_X
                    d_pitch = (((y1 + y2) / 2) - CY) * DEG_PER_PIX_Y
                    cross_dist = np.sqrt(d_yaw**2 + d_pitch**2)
                    dist_3d = min(DISTANCE_CONSTANT / max(y2 - y1, 1), 2500)

                    COMBAT_HISTORY.append({'cross_dist': cross_dist})
                    w_class = map_weapon_class(gsi['weapon'])

                    feature_vector = np.array([[
                        gsi['health'], gsi['armor'], gsi['ammo'],
                        gsi.get('ducking', 0), gsi.get('scoped', 0),
                        gsi.get('is_moving', 0), gsi.get('is_reloading', 0),
                        dist_3d, d_yaw, d_pitch, cross_dist, 1,
                        w_class['class_sniper'], w_class['class_rifle'], w_class['class_smg'],
                        w_class['class_pistol'], w_class['class_heavy']
                    ]])

                    now = time.time()
                    feature_names = getattr(combat_model, "feature_names_in_", MODEL_FEATURES)
                    feature_df = pd.DataFrame(feature_vector, columns=feature_names)
                    prediction = int(combat_model.predict(feature_df)[0])

                    if prediction == 1:
                        command_text = "OPTIMAL ENGAGEMENT - FIRE!"
                    else:
                        command_text = "HOLD - BAD ENGAGE"

                    if prediction != last_prediction or now - last_engage_time > ENGAGE_COOLDOWN:
                        if command_text != last_display_text:
                            overlay.update_text(command_text)
                            last_display_text = command_text
                        if prediction == 1:
                            log.info("ENGAGEMENT TRIGGERED")
                        last_engage_time = now
                        last_prediction = prediction

            if not enemy_detected:
                now = time.time()
                if now - last_enemy_seen > NO_ENEMY_GRACE and last_display_text != DEFAULT_OVERLAY_TEXT:
                    overlay.update_text(DEFAULT_OVERLAY_TEXT)
                    last_display_text = DEFAULT_OVERLAY_TEXT
                    last_prediction = None

        except Exception as e:
            log.error(f"Vision engine loop error: {e}\n{traceback.format_exc()}")
            time.sleep(0.1)



def run_igl_engine(overlay):
    log.info("IGL engine starting...")
    memory = OpponentMemoryMatrix()

    try:
        eco_tracker = EnemyEconomyTracker()
        log.info("IGL engine ready.")
    except Exception as e:
        log.critical(f"IGL engine failed to initialize: {e}\n{traceback.format_exc()}")
        return

    last_phase, round_num = "unknown", 1

    while True:
        try:
            with state_lock:
                phase = CURRENT_GSI['round_phase']

            if phase == "freezetime" and last_phase != "freezetime":
                log.info(f"--- Freezetime detected (Round {round_num}) ---")

                with state_lock:
                    enemy_score = CURRENT_GSI['enemy_score']
                    loss_bonus = CURRENT_GSI['enemy_loss_bonus']
                    money = CURRENT_GSI['money']

                eco_status = eco_tracker.update(enemy_score, loss_bonus)

                if GROQ_AVAILABLE:
                    try:
                        sys_prompt = (
                            "You are Apex, a professional CS2 (Counter-Strike 2) IGL coach and Adaptive Player Experience Coach. "
                            "Respond in EXACTLY one short sentence. ONLY mention real CS2 items. "
                            "VALID CS2 BUY OPTIONS: "
                            "Rifles: AK-47 ($2700 T-side), M4A4 ($3100 CT), M4A1-S ($2900 CT). "
                            "Snipers: AWP ($4750), SSG08 ($1700). "
                            "SMGs: MP9 ($1250 CT), MAC-10 ($1050 T), UMP-45 ($1200). "
                            "Pistols: Desert Eagle ($700), P250 ($300), Five-SeveN ($500 CT), Tec-9 ($500 T). "
                            "Utility: Smoke ($300), Flashbang ($200), HE Grenade ($300), Molotov ($400 T) / Incendiary ($600 CT). "
                            "Armor: Kevlar ($650), Kevlar+Helmet ($1000). "
                            "STRATEGY RULES: Under $2000 = ECO (pistol only, save money). "
                            "$2000-$3500 = FORCE BUY (SMG or pistol + utility). "
                            "Over $3500 = FULL BUY (rifle + Kevlar+Helmet + 1-2 utility). "
                            f"Enemy predicted economy: {eco_status}. "
                            f"Recent round history: {memory.get_context() or 'Round 1, no history yet'}."
                        )
                        user_msg = f"I have ${money}. What should I buy this round?"

                        completion = groq_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": sys_prompt},
                                {"role": "user", "content": user_msg}
                            ],
                            model="llama-3.1-8b-instant",
                            temperature=0.7,
                        )

                        apex_call = completion.choices[0].message.content.replace('"', '')

                    except Exception as e:
                        log.error(f"Groq API call failed: {type(e).__name__}: {e}")
                        apex_call = f"API error ({type(e).__name__}). Play default."
                else:
                    apex_call = f"Hold defaults. {eco_status}."

                overlay.update_eco(eco_status)
                speak(apex_call)  

                memory.log_round(round_num, apex_call)
                round_num += 1

            last_phase = phase

        except Exception as e:
            log.error(f"IGL engine loop error: {e}\n{traceback.format_exc()}")

        time.sleep(0.5)

# ==========================================
# 6. EXECUTION
# ==========================================
if __name__ == "__main__":
    log.info("=== Apex starting up ===")
    overlay = ApexOverlay()

    if not GROQ_AVAILABLE:
        overlay.update_text("Warning: GROQ_API_KEY missing. LLM offline.")

    threading.Thread(target=tts_worker, daemon=True).start()
    
    threading.Thread(target=lambda: HTTPServer(('127.0.0.1', 3000), GSIServer).serve_forever(), daemon=True).start()
    camera = dxcam.create(output_idx=0, output_color="BGR")
    thread = threading.Thread(target=run_vision_engine, args=(overlay, camera))
    thread.start()
    threading.Thread(target=run_igl_engine, args=(overlay,), daemon=True).start()
    
    threading.Thread(target=lambda: boot_sequence(overlay), daemon=True).start()

    log.info("All threads launched. Starting overlay mainloop.")
    overlay.root.mainloop()