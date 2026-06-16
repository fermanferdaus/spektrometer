import time
import numpy as np
import config

# --- State Global ---
sensor_data = {"intensity_lux": 0.0, "wavelength": 0.0}
dark_lux_offset = 0.0
raw_lux = 0.0

experiment_state = {
    "recording": False,
    "current": -1,
    "experiments": [],
}


def get_experiment_label(index):
    """Mendapatkan label nama percobaan berdasarkan index."""
    offset = 0
    for group in config.EXPERIMENT_GROUPS:
        if index < offset + group["trials"]:
            trial_num = index - offset + 1
            return f'{group["name"]} \u2014 Ulangan {trial_num}'
        offset += group["trials"]
    return f"Percobaan {index + 1}"


def get_experiment_group_info(index):
    """Mendapatkan nama grup eksperimen dan nomor ulangan berdasarkan index."""
    offset = 0
    for group in config.EXPERIMENT_GROUPS:
        if index < offset + group["trials"]:
            return group["name"], index - offset + 1
        offset += group["trials"]
    return "Unknown", 0


def build_spectrum(exp):
    """Konversi akumulasi kolom ROI menjadi list [{wl, lux}] untuk grafik."""
    if exp["spectrum_accum"] is None or exp["frame_count"] == 0:
        return []

    avg = exp["spectrum_accum"] / exp["frame_count"]
    roi_w = len(avg)
    spectrum = []
    for col in range(roi_w):
        wl = config.WL_MIN + (col / max(roi_w - 1, 1)) * (config.WL_MAX - config.WL_MIN)
        lux_val = (float(avg[col]) / 255.0) * 1000
        spectrum.append({"wl": round(wl, 1), "lux": round(lux_val, 2)})
    return spectrum


def condense_spectrum(spectrum, n=10):
    """Ambil n titik data representatif yang tersebar merata di rentang panjang gelombang."""
    if not spectrum or len(spectrum) <= n:
        return spectrum

    total = len(spectrum)
    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]

    return [spectrum[i] for i in indices]


def compute_absorbance():
    """Hitung absorbansi dari seluruh percobaan (9 percobaan)."""
    if len(experiment_state["experiments"]) < config.MAX_EXPERIMENTS:
        return None
    for exp in experiment_state["experiments"]:
        if exp["frame_count"] == 0:
            return None

    # Kumpulkan spektrum per grup
    offset = 0
    group_spectra = {}
    for group in config.EXPERIMENT_GROUPS:
        name = group["name"]
        spectra = []
        for i in range(group["trials"]):
            idx = offset + i
            spectrum = build_spectrum(experiment_state["experiments"][idx])
            if spectrum:
                spectra.append(spectrum)
        group_spectra[name] = spectra
        offset += group["trials"]

    # Rata-rata setiap grup
    def avg_spectra(sp_list):
        if not sp_list:
            return []
        n = len(sp_list)
        length = min(len(s) for s in sp_list)
        result = []
        for j in range(length):
            avg_lux = sum(s[j]["lux"] for s in sp_list) / n
            result.append({"wl": sp_list[0][j]["wl"], "lux": round(avg_lux, 4)})
        return result

    avg_blank = avg_spectra(group_spectra.get("Kuvet Kosong", []))
    avg_ref = avg_spectra(group_spectra.get("Aquadest (I\u2080)", []))
    avg_sample = avg_spectra(group_spectra.get("Larutan Pewarna Makanan (I)", []))

    # Hitung Absorbansi per panjang gelombang
    if avg_blank:
        length = min(len(avg_ref), len(avg_sample), len(avg_blank))
    else:
        length = min(len(avg_ref), len(avg_sample))

    raw_a = []
    # Cari nilai intensitas maksimum referensi untuk threshold noise
    max_i0 = max((ref["lux"] for ref in avg_ref), default=1.0)
    threshold = max_i0 * 0.02  # Abaikan ujung spektrum yang intensitasnya < 2% dari puncak

    for j in range(length):
        wl = avg_ref[j]["wl"]
        i0 = avg_ref[j]["lux"]
        i_s = avg_sample[j]["lux"]

        if i0 > threshold:
            t = i_s / i0
            if t <= 0.001:
                t = 0.001
            a = -np.log10(t)
            a = max(0.0, a) # Absorbansi tidak boleh negatif
        else:
            a = 0.0

        raw_a.append({"wl": wl, "A": a})

    # Smoothing (Moving Average) agar grafik tidak bergerigi (noise)
    window_size = 15
    half_window = window_size // 2
    absorbance = []
    
    for i in range(len(raw_a)):
        start = max(0, i - half_window)
        end = min(len(raw_a), i + half_window + 1)
        avg_a = sum(item["A"] for item in raw_a[start:end]) / (end - start)
        absorbance.append({"wl": raw_a[i]["wl"], "A": round(avg_a, 4)})

    return {
        "avg_blank": avg_blank,
        "avg_reference": avg_ref,
        "avg_sample": avg_sample,
        "absorbance": absorbance,
    }


def reset_experiments():
    """Reset data percobaan ke state awal."""
    experiment_state["current"] = -1
    experiment_state["experiments"] = []
