import random
import json
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# CONFIGURATION & CONSTANTS (300 DPI A4)
# ---------------------------------------------------------
A4_WIDTH = 2480
A4_HEIGHT = 3508
COLS = 2
ROWS = 4
BOX_WIDTH = 1190  
BOX_HEIGHT = 852
MARGIN_X = 50
MARGIN_Y = 50

BASE_URL = "https://qr-hunt.streamlit.app/?code="

# Generate unique 6-digit codes
all_codes = set()
while len(all_codes) < 30:
    all_codes.add(str(random.randint(100000, 999999)))

all_codes_list = list(all_codes)
special_codes = all_codes_list[:5]    
normal_codes = all_codes_list[5:]     

# Save Firebase initialization payload
firebase_payload = {
    "valid_codes": {
        "normal": normal_codes,
        "special": special_codes
    }
}
with open("firebase_codes.json", "w") as f:
    json.dump(firebase_payload, f, indent=2)

print("✅ Firebase JSON payload exported to 'firebase_codes.json'")

# ---------------------------------------------------------
# FONT LOADING ENGINE
# ---------------------------------------------------------
try:
    # Windows standard paths
    title_font = ImageFont.truetype("arial.ttf", 75)       # Big header font
    medium_font = ImageFont.truetype("arial.ttf", 42)      # Fair play / Special tag font
    id_font = ImageFont.truetype("arial.ttf", 32)          # Small subtle font for the Code ID
except IOError:
    try:
        # Mac/Linux fallback paths
        title_font = ImageFont.truetype("Helvetica-Bold", 75)
        medium_font = ImageFont.truetype("Helvetica", 42)
        id_font = ImageFont.truetype("Helvetica", 32)
    except IOError:
        print("Could not load system TTF fonts, using basic scaling.")
        title_font = ImageFont.load_default()
        medium_font = ImageFont.load_default()
        id_font = ImageFont.load_default()

# ---------------------------------------------------------
# IMAGE COMPOSITING ENGINE
# ---------------------------------------------------------
def create_qr_image(data):
    """Generates a high-contrast black & white QR code."""
    qr = qrcode.QRCode(version=1, box_size=15, border=1)
    qr.add_data(f"{BASE_URL}{data}")
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")

pages = []
current_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
draw = ImageDraw.Draw(current_page)

for total_index, code_id in enumerate(all_codes_list):
    is_special = code_id in special_codes
    
    # Calculate grid layout positions
    local_index = total_index % (COLS * ROWS)
    col = local_index % COLS
    row = local_index // COLS
    
    x1 = MARGIN_X + (col * BOX_WIDTH)
    y1 = MARGIN_Y + (row * BOX_HEIGHT)
    x2 = x1 + BOX_WIDTH
    y2 = y1 + BOX_HEIGHT
    
    # Draw cutting guides around the cutout boxes
    draw.rectangle([x1, y1, x2, y2], outline="#d0d0d0", width=3)
    
    # 1. Header Title
    title_text = "• QR HUNT •"
    draw.text((x1 + BOX_WIDTH//2, y1 + 100), title_text, fill="black", font=title_font, anchor="mm")
    
    # 2. Generate and place the QR Code graphic element
    qr_size = 480
    qr_img = create_qr_image(code_id)
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    
    qr_x = x1 + (BOX_WIDTH - qr_size) // 2
    qr_y = y1 + (BOX_HEIGHT - qr_size) // 2
    current_page.paste(qr_img, (qr_x, qr_y))
    
    # 3. Code ID placement (Small font directly under the QR block)
    id_y_position = qr_y + qr_size + 25
    draw.text((x1 + BOX_WIDTH//2, id_y_position), f"ID: {code_id}", fill="black", font=id_font, anchor="mm")
    
    # 4. Footer Label (Dynamic conditioning based on node type tier)
    if is_special:
        special_text = "SPECIAL CACHE (+30 PTS)"
        draw.text((x1 + BOX_WIDTH//2, y2 - 95), special_text, fill="black", font=medium_font, anchor="mm")
    else:
        fair_play_text = "FAIR PLAY: Leave me in my place for the next Hunter!"
        draw.text((x1 + BOX_WIDTH//2, y2 - 95), fair_play_text, fill="black", font=medium_font, anchor="mm")
    
    # If the sheet is filled up or it's the last item, save and spin up a new page canvas
    if local_index == (COLS * ROWS - 1) or total_index == len(all_codes_list) - 1:
        pages.append(current_page)
        current_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), "white")
        draw = ImageDraw.Draw(current_page)

# Compile everything into a crisp single document 
if pages:
    pages[0].save(
        "game_codes_printout.pdf",
        save_all=True,
        append_images=pages[1:],
        resolution=300.0,
        quality=100
    )
    print("✅ Fixed master print document built: 'game_codes_printout.pdf'")