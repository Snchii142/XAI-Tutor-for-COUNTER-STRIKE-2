import os
import json
import winreg
import glob
import re

CONFIG_FILE = "apex_config.json"

def get_true_cs2_resolution():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
        search_path = os.path.join(steam_path, "userdata", "*", "730", "local", "cfg", "cs2_video.txt")
        config_files = glob.glob(search_path)
        
        if not config_files: return None
            
        latest_config = max(config_files, key=os.path.getmtime)
        with open(latest_config, 'r') as f:
            content = f.read()
            
        width_match = re.search(r'"setting\.defaultres"\s+"(\d+)"', content)
        height_match = re.search(r'"setting\.defaultresheight"\s+"(\d+)"', content)
        
        if width_match and height_match:
            width = int(width_match.group(1))
            height = int(height_match.group(1))
            
            ratio = width / height
            aspect = "16:9" if ratio > 1.7 else "16:10" if ratio > 1.5 else "4:3"
            return {"width": width, "height": height, "aspect": aspect}
    except Exception:
        return None

def load_config():
    if not os.path.exists(CONFIG_FILE):
        auto_settings = get_true_cs2_resolution()
        if auto_settings:
            cfg = {
                "screen_width": auto_settings["width"], "screen_height": auto_settings["height"],
                "aspect_ratio": auto_settings["aspect"], "distance_constant": 66440
            }
        else:
            # Hardcoded fallback for 1568x1080 stretched setup
            cfg = {
                "screen_width": 1568, "screen_height": 1080,
                "aspect_ratio": "4:3", "distance_constant": 66440
            }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
            
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

cfg = load_config()
SCREEN_WIDTH, SCREEN_HEIGHT = cfg["screen_width"], cfg["screen_height"]
CX, CY = SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2
DISTANCE_CONSTANT = cfg["distance_constant"]
FOV_Y = 74.0

if cfg["aspect_ratio"] == "16:9": FOV_X = 90.0
elif cfg["aspect_ratio"] == "4:3": FOV_X = 73.74
elif cfg["aspect_ratio"] == "16:10": FOV_X = 84.0
else: FOV_X = 90.0

if cfg["screen_width"] == 1568 and cfg["aspect_ratio"] == "4:3":
    FOV_X = 90.0

DEG_PER_PIX_X = FOV_X / SCREEN_WIDTH
DEG_PER_PIX_Y = FOV_Y / SCREEN_HEIGHT