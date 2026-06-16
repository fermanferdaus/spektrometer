import os
import time
import numpy as np
import cv2
import state
import config
import threading
import logging

# Suppress noisy OpenCV obsensor errors
os.environ["OPENCV_LOG_LEVEL"] = "WARNING"

logger = logging.getLogger(__name__)

# --- State EMA (Exponential Moving Average) ---
_ema_lux = 0.0
_ema_wl = 0.0
_ema_initialized = False

# --- Kamera State ---
_lock = threading.Lock()
cap = None
_active_camera_index = -1
_camera_error = None
_camera_gen = 0  # Incremented on every camera switch for change detection
_cached_cameras = []


def scan_cameras(max_check=4, force=False):
    """Mendeteksi semua kamera yang tersedia di sistem."""
    global _cached_cameras
    if not force and _cached_cameras:
        return _cached_cameras

    available = []
    consecutive_fail = 0

    for i in range(max_check):
        test = None
        found = False
        try:
            test = cv2.VideoCapture(i)
            if test is not None and test.isOpened():
                ret = False
                for _ in range(5):  # Tambah menjadi 5 attempt
                    ret, _ = test.read()
                    if ret:
                        break
                    time.sleep(0.1)  # Wajib ada delay agar MSMF sempat warm-up
                if ret:
                    w = int(test.get(cv2.CAP_PROP_FRAME_WIDTH))
                    h = int(test.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    available.append({
                        "index": i,
                        "name": f"Kamera {i} (Internal/Laptop)" if i == 0 else f"Kamera {i} (External)",
                        "resolution": f"{w}x{h}",
                    })
                    found = True
                    consecutive_fail = 0
        except Exception:
            pass
        finally:
            if test is not None:
                try:
                    test.release()
                except Exception:
                    pass

        if not found:
            consecutive_fail += 1
            # Berhenti scan jika 2 index berturut-turut gagal (hemat waktu)
            if consecutive_fail >= 2 and len(available) > 0:
                break

    _cached_cameras = available
    return available


def _lock_camera_settings(capture):
    """Mengunci auto-exposure, auto-gain, dan auto-WB webcam (best-effort)."""
    try:
        capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        capture.set(cv2.CAP_PROP_AUTO_WB, 0)
        capture.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    except Exception:
        pass


def _hue_to_wavelength(hue):
    """Konversi Hue OpenCV (0-180) ke panjang gelombang (nm) via interpolasi piecewise-linear."""
    table = config.HUE_TO_WL_TABLE

    if hue <= table[0][0]:
        return table[0][1]
    if hue >= table[-1][0]:
        return table[-1][1]

    for i in range(len(table) - 1):
        h0, wl0 = table[i]
        h1, wl1 = table[i + 1]
        if h0 <= hue <= h1:
            t = (hue - h0) / max(h1 - h0, 1e-6)
            return wl0 + t * (wl1 - wl0)

    return table[-1][1]


def switch_camera(index):
    """Berpindah ke kamera dengan index tertentu. Thread-safe."""
    global cap, _active_camera_index, _camera_error, _camera_gen

    with _lock:
        old_cap = cap
        cap = None
        _camera_error = None

        # Release kamera lama
        if old_cap is not None:
            try:
                old_cap.release()
            except Exception:
                pass

        try:
            new_cap = cv2.VideoCapture(index)

            if new_cap is None or not new_cap.isOpened():
                _camera_error = f"Kamera {index} tidak dapat dibuka."
                _active_camera_index = -1
                _camera_gen += 1
                return False, _camera_error

            # MSMF backend kadang gagal grab frame pertama, coba retry
            ret = False
            for _ in range(3):
                ret, _ = new_cap.read()
                if ret:
                    break
                time.sleep(0.1)

            if not ret:
                new_cap.release()
                _camera_error = f"Kamera {index} tidak merespons."
                _active_camera_index = -1
                _camera_gen += 1
                return False, _camera_error

            _lock_camera_settings(new_cap)
            cap = new_cap
            _active_camera_index = index
            _camera_gen += 1
            logger.info(f"Berhasil beralih ke kamera index={index}")
            return True, f"Berhasil beralih ke Kamera {index}."

        except Exception as e:
            _camera_error = f"Error membuka kamera {index}: {str(e)}"
            _active_camera_index = -1
            _camera_gen += 1
            logger.error(_camera_error)
            return False, _camera_error


def _try_recover_camera():
    """Mencoba recovery otomatis saat kamera aktif mati — fallback ke kamera lain."""
    global _camera_error
    cameras = scan_cameras()
    if not cameras:
        _camera_error = "Tidak ada kamera yang terdeteksi."
        return False

    sorted_cams = sorted(cameras, key=lambda c: c["index"])
    for cam in sorted_cams:
        ok, msg = switch_camera(cam["index"])
        if ok:
            _camera_error = None
            return True

    _camera_error = "Gagal recovery ke kamera manapun."
    return False


def get_camera_status():
    """Mengembalikan status kamera aktif saat ini."""
    return {
        "active_index": _active_camera_index,
        "is_connected": cap is not None and cap.isOpened(),
        "error": _camera_error,
    }


def init_camera():
    """Inisialisasi kamera saat startup — coba kamera 1 (external) dulu, lalu fallback ke 0."""
    cameras = scan_cameras()
    if not cameras:
        logger.warning("Tidak ada kamera terdeteksi saat startup.")
        return

    external = [c for c in cameras if c["index"] == 1]
    if external:
        ok, _ = switch_camera(1)
        if ok:
            return

    ok, _ = switch_camera(cameras[0]["index"])
    if not ok:
        logger.warning("Gagal menginisialisasi kamera manapun.")


# Inisialisasi saat modul diimpor
init_camera()


def get_cap():
    return cap


def release_camera():
    """Merilis resource webcam capture."""
    global cap, _active_camera_index
    with _lock:
        if cap is not None:
            cap.release()
            cap = None
        _active_camera_index = -1


def capture_image(image_path):
    """Mengambil satu frame dari kamera dan menyimpan sebagai gambar."""
    current_cap = cap
    if current_cap is None or not current_cap.isOpened():
        if not _try_recover_camera():
            return False
        current_cap = cap

    try:
        ok, frame = current_cap.read()
    except Exception:
        ok = False

    if not ok:
        if _try_recover_camera() and cap is not None:
            try:
                ok, frame = cap.read()
            except Exception:
                ok = False
        if not ok:
            return False

    roi = frame
    if roi.size > 0:
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        col_brightness = hsv[:, :, 2].mean(axis=0).astype(float)

        return {
            "frame": frame,
            "spectrum": col_brightness.copy(),
            "saved": cv2.imwrite(image_path, frame),
        }

    return None


def _make_placeholder(text1="Kamera tidak terdeteksi", text2="Pilih kamera di menu pengaturan"):
    """Buat frame placeholder hitam dengan teks."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(blank, text1, (80, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    cv2.putText(blank, text2, (70, 260),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 80), 1)
    _, buf = cv2.imencode(".jpg", blank)
    return (b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")


def generate_frames():
    """Generator MJPEG frames + hitung data sensor real-time."""
    global _ema_lux, _ema_wl, _ema_initialized

    local_gen = _camera_gen
    consecutive_failures = 0
    MAX_FAILURES = 10

    while True:
        # Deteksi apakah kamera telah di-switch oleh thread lain
        if local_gen != _camera_gen:
            local_gen = _camera_gen
            consecutive_failures = 0
            # Langsung lanjut baca dari kamera baru tanpa delay
            continue

        current_cap = cap
        if current_cap is None or not current_cap.isOpened():
            yield _make_placeholder()
            time.sleep(1)
            continue

        try:
            ok, frame = current_cap.read()
        except Exception:
            ok = False
            frame = None

        if not ok:
            consecutive_failures += 1
            if consecutive_failures >= MAX_FAILURES:
                consecutive_failures = 0
                _try_recover_camera()
            time.sleep(0.05)
            continue

        consecutive_failures = 0
        roi = frame

        if roi.size > 0:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # --- Intensitas Cahaya (dari seluruh frame) ---
            avg_v = float(hsv[:, :, 2].mean())
            raw_lux = (avg_v / 255.0) * 1000
            state.raw_lux = raw_lux

            lux = max(0.0, raw_lux - state.dark_lux_offset)

            # --- Panjang Gelombang (dari piksel chromatic saja) ---
            mask = (hsv[:, :, 1] >= config.SAT_THRESHOLD) & (hsv[:, :, 2] >= config.VAL_THRESHOLD)
            total_pixels = hsv.shape[0] * hsv.shape[1]
            chromatic_count = int(mask.sum())

            if lux <= 0.01:
                raw_wl = 0.0
                lux = 0.0
            elif chromatic_count < total_pixels * config.MIN_CHROMATIC_RATIO:
                raw_wl = 0.0
            else:
                hue_values = hsv[:, :, 0][mask]
                hist = cv2.calcHist(
                    [hue_values.reshape(-1, 1).astype(np.uint8)],
                    [0], None, [180], [0, 180]
                )
                dominant_hue = float(np.argmax(hist))
                raw_wl = _hue_to_wavelength(dominant_hue)

            # --- EMA Smoothing ---
            if not _ema_initialized:
                _ema_lux = lux
                _ema_wl = raw_wl
                _ema_initialized = True
            else:
                alpha = config.EMA_ALPHA
                _ema_lux = _ema_lux + alpha * (lux - _ema_lux)

                if raw_wl == 0.0 and _ema_wl > 0:
                    _ema_wl = _ema_wl * (1 - alpha)
                    if _ema_wl < 1.0:
                        _ema_wl = 0.0
                else:
                    _ema_wl = _ema_wl + alpha * (raw_wl - _ema_wl)

            state.sensor_data["intensity_lux"] = round(_ema_lux, 2)
            state.sensor_data["wavelength"] = round(_ema_wl, 2)

        _, buf = cv2.imencode(".jpg", frame)
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

