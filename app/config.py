import os

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "captures")
os.makedirs(IMAGE_DIR, exist_ok=True)

# --- Konfigurasi Percobaan ---
EXPERIMENT_GROUPS = [
    {"name": "Kuvet Kosong", "trials": 3},
    {"name": "Aquadest (I\u2080)", "trials": 3},
    {"name": "Larutan Pewarna Makanan (I)", "trials": 3},
]

MAX_EXPERIMENTS = sum(g["trials"] for g in EXPERIMENT_GROUPS)

# Rentang panjang gelombang spektrum visible (nm)
WL_MIN = 380
WL_MAX = 700

# --- Konfigurasi Sensor ---

# Threshold minimum Saturation (0-255) — piksel di bawah ini dianggap achromatic
SAT_THRESHOLD = 40

# Threshold minimum Value/Brightness (0-255) — piksel di bawah ini terlalu gelap
VAL_THRESHOLD = 30

# Faktor smoothing EMA (0 < α ≤ 1). Semakin kecil = semakin halus, semakin lambat respons
EMA_ALPHA = 0.25

# Rasio minimum piksel chromatic terhadap total piksel agar pembacaan warna valid
MIN_CHROMATIC_RATIO = 0.05

# Tabel kalibrasi Hue OpenCV (0-180) → Panjang Gelombang (nm)
# Format: (hue_opencv, wavelength_nm)
HUE_TO_WL_TABLE = [
    (0,   650),
    (5,   640),
    (10,  620),
    (15,  610),
    (22,  590),
    (30,  580),
    (38,  570),
    (50,  555),
    (65,  520),
    (80,  500),
    (95,  488),
    (105, 475),
    (115, 460),
    (125, 445),
    (135, 430),
    (145, 410),
    (155, 400),
    (170, 650),
    (180, 650),
]
