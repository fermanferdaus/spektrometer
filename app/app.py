import os
import shutil
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response
import uvicorn
import urllib.parse

import config
import state
import camera
import exporter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Webcam Spectrophotometer")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("shutdown")
def shutdown_event():
    """Menghentikan dan merilis kamera saat aplikasi shutdown."""
    camera.release_camera()


# --- Camera Management Routes ---

@app.get("/api/camera/list")
def camera_list(refresh: bool = False):
    """Mendeteksi dan menampilkan semua kamera yang tersedia."""
    cameras = camera.scan_cameras(force=refresh)
    status = camera.get_camera_status()
    return {
        "success": True,
        "cameras": cameras,
        "active_index": status["active_index"],
        "is_connected": status["is_connected"],
        "error": status["error"],
    }


@app.post("/api/camera/switch/{index}")
def camera_switch(index: int):
    """Berpindah ke kamera dengan index tertentu."""
    ok, message = camera.switch_camera(index)
    status = camera.get_camera_status()
    return {
        "success": ok,
        "message": message,
        "active_index": status["active_index"],
        "is_connected": status["is_connected"],
    }


@app.get("/api/camera/status")
def camera_status():
    """Mengembalikan status kamera aktif saat ini."""
    status = camera.get_camera_status()
    return {
        "success": True,
        **status,
    }


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        camera.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/data")
def api_data():
    return state.sensor_data


@app.get("/api/experiment/status")
def experiment_status():
    exps = []
    for i, exp in enumerate(state.experiment_state["experiments"]):
        group_name, trial_num = state.get_experiment_group_info(i)
        spectrum = state.build_spectrum(exp)
        condensed = state.condense_spectrum(spectrum, n=10)

        exps.append({
            "index": i,
            "label": state.get_experiment_label(i),
            "group": group_name,
            "trial": trial_num,
            "sample_count": len(condensed),
            "samples": condensed,
            "has_image": exp.get("image_path") is not None,
            "updated_at": exp.get("captured_at") or 0,
        })

    current_idx = state.experiment_state["current"]
    if current_idx != -1:
        next_idx = current_idx
    else:
        # Cari index pertama yang kosong/belum selesai
        next_idx = -1
        for i, exp in enumerate(state.experiment_state["experiments"]):
            if exp["frame_count"] == 0:
                next_idx = i
                break
        if next_idx == -1:
            next_idx = len(state.experiment_state["experiments"])

    next_label = state.get_experiment_label(next_idx) if next_idx < config.MAX_EXPERIMENTS else None
    total_done = sum(1 for exp in state.experiment_state["experiments"] if exp["frame_count"] > 0)

    return {
        "recording": False,
        "current": state.experiment_state["current"],
        "max": config.MAX_EXPERIMENTS,
        "total_done": total_done,
        "next_label": next_label,
        "groups": [g["name"] for g in config.EXPERIMENT_GROUPS],
        "experiments": exps,
    }


@app.post("/api/experiment/capture")
def experiment_capture():
    """Mengambil satu gambar untuk percobaan saat ini."""
    idx = state.experiment_state["current"]
    if idx == -1:
        # Cari index pertama yang kosong/belum selesai
        for i, exp in enumerate(state.experiment_state["experiments"]):
            if exp["frame_count"] == 0:
                idx = i
                break
        if idx == -1:
            idx = len(state.experiment_state["experiments"])

    if idx >= config.MAX_EXPERIMENTS:
        return {"success": False, "message": f"Sudah mencapai batas {config.MAX_EXPERIMENTS} percobaan."}

    state.experiment_state["current"] = idx
    label = state.get_experiment_label(idx)

    # Jika index ini baru, append
    if idx >= len(state.experiment_state["experiments"]):
        state.experiment_state["experiments"].append({
            "spectrum_accum": None,
            "frame_count": 0,
            "image_path": None,
            "label": label,
            "captured_at": None,
        })
    else:
        # Jika mengulang yang sudah ada, bersihkan datanya terlebih dahulu
        exp = state.experiment_state["experiments"][idx]
        ip = exp.get("image_path")
        if ip and os.path.exists(ip):
            try:
                os.remove(ip)
            except OSError:
                pass
        exp["spectrum_accum"] = None
        exp["frame_count"] = 0
        exp["image_path"] = None
        exp["captured_at"] = None

    # Ambil gambar
    image_path = os.path.join(config.IMAGE_DIR, f"percobaan_{idx + 1}.jpg")
    result = camera.capture_image(image_path)

    if result is None or result is False:
        state.experiment_state["current"] = -1
        return {"success": False, "message": "Gagal mengambil gambar dari kamera."}

    exp = state.experiment_state["experiments"][idx]
    exp["image_path"] = image_path
    exp["captured_at"] = time.time()
    exp["spectrum_accum"] = result["spectrum"].copy()
    exp["frame_count"] = 1

    state.experiment_state["current"] = -1

    return {"success": True, "message": f"{label} berhasil diambil.", "experiment_index": idx}


@app.post("/api/experiment/reset")
def experiment_reset():
    # Hapus folder captures beserta isinya
    if os.path.exists(config.IMAGE_DIR):
        try:
            shutil.rmtree(config.IMAGE_DIR)
        except OSError:
            pass

    # Buat kembali folder captures kosong
    os.makedirs(config.IMAGE_DIR, exist_ok=True)

    state.reset_experiments()

    return {"success": True, "message": "Semua percobaan telah direset."}


@app.post("/api/experiment/calibrate_dark")
def experiment_calibrate_dark():
    state.dark_lux_offset = state.raw_lux
    return {
        "success": True,
        "message": f"Kalibrasi gelap berhasil. Offset: {round(state.dark_lux_offset, 2)} Lux.",
        "offset": state.dark_lux_offset
    }


@app.post("/api/experiment/redo/{index}")
def experiment_redo(index: int):
    if index < 0 or index >= len(state.experiment_state["experiments"]):
        return {"success": False, "message": "Index tidak valid."}

    state.experiment_state["current"] = index

    exp = state.experiment_state["experiments"][index]
    ip = exp.get("image_path")
    if ip and os.path.exists(ip):
        try:
            os.remove(ip)
        except OSError:
            pass
    exp["spectrum_accum"] = None
    exp["frame_count"] = 0
    exp["image_path"] = None
    exp["captured_at"] = None

    return {"success": True, "message": f"Siap mengulangi {state.get_experiment_label(index)}."}


@app.post("/api/experiment/delete/{index}")
def experiment_delete(index: int):
    if index < 0 or index >= len(state.experiment_state["experiments"]):
        return {"success": False, "message": "Index tidak valid."}

    exp = state.experiment_state["experiments"][index]
    ip = exp.get("image_path")
    if ip and os.path.exists(ip):
        try:
            os.remove(ip)
        except OSError:
            pass

    if index == len(state.experiment_state["experiments"]) - 1:
        state.experiment_state["experiments"].pop()
        # Hapus juga semua element kosong yang berada di ujung
        while state.experiment_state["experiments"] and state.experiment_state["experiments"][-1]["frame_count"] == 0:
            state.experiment_state["experiments"].pop()
    else:
        exp["spectrum_accum"] = None
        exp["frame_count"] = 0
        exp["image_path"] = None
        exp["captured_at"] = None

    state.experiment_state["current"] = -1

    return {"success": True, "message": "Percobaan berhasil dihapus."}


@app.get("/api/experiment/image/{index}")
def experiment_image(index: int, download: int = 0):
    if index < 0 or index >= len(state.experiment_state["experiments"]):
        return {"success": False, "message": "Index tidak valid."}
    ip = state.experiment_state["experiments"][index].get("image_path")
    if ip and os.path.exists(ip):
        if download == 1:
            label = state.get_experiment_label(index)
            # Bersihkan nama file dari karakter khusus
            filename = label.replace(" ", "_").replace("(", "").replace(")", "").replace("—", "-")
            filename = f"{filename}.jpg"
            return FileResponse(ip, media_type="image/jpeg", filename=filename)
        return FileResponse(ip, media_type="image/jpeg")
    return {"success": False, "message": "File gambar tidak ditemukan."}


@app.get("/api/experiment/excel/{index}")
def experiment_excel(index: int):
    """Export data spektrum percobaan ke file Excel."""
    if index < 0 or index >= len(state.experiment_state["experiments"]):
        return {"success": False, "message": "Index tidak valid."}

    exp = state.experiment_state["experiments"][index]
    spectrum = state.build_spectrum(exp)
    if not spectrum:
        return {"success": False, "message": "Belum ada data spektrum."}

    # Ambil 10 titik data representatif untuk export
    condensed = state.condense_spectrum(spectrum, n=10)

    label = state.get_experiment_label(index)

    buf = exporter.export_experiment_excel(label, condensed)

    translation_table = str.maketrans({
        "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
        "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
        "—": "-", "–": "-"
    })
    fallback_label = label.translate(translation_table)
    fallback_label = fallback_label.encode("ascii", "ignore").decode("ascii")
    fallback_name = fallback_label.replace(" ", "_").replace("(", "").replace(")", "")
    if not fallback_name or fallback_name == ".xlsx":
        fallback_name = f"percobaan_{index + 1}"
    fallback_filename = f"{fallback_name}.xlsx"

    utf8_name = label.replace(" ", "_").replace("(", "").replace(")", "")
    utf8_filename = f"{utf8_name}.xlsx"
    encoded_filename = urllib.parse.quote(utf8_filename)

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=\"{fallback_filename}\"; filename*=utf-8''{encoded_filename}"},
    )


@app.get("/api/experiment/absorbance")
def experiment_absorbance():
    result = state.compute_absorbance()
    if result is None:
        return {"success": False, "message": "Belum semua 9 percobaan selesai."}
        
    # Samakan data dengan export Excel agar grafiknya sama-sama mulus (condensed)
    # Kita gunakan 15 titik agar tetap smooth tapi tidak terlalu kaku
    condensed_result = {
        "avg_blank": state.condense_spectrum(result["avg_blank"], n=15),
        "avg_reference": state.condense_spectrum(result["avg_reference"], n=15),
        "avg_sample": state.condense_spectrum(result["avg_sample"], n=15),
        "absorbance": state.condense_spectrum(result["absorbance"], n=15),
    }
    
    return {"success": True, **condensed_result}


@app.get("/api/experiment/absorbance/excel")
def experiment_absorbance_excel():
    """Export hasil absorbansi ke Excel."""
    result = state.compute_absorbance()
    if result is None:
        return {"success": False, "message": "Belum semua 9 percobaan selesai."}

    # Kondensasi semua data ke 15 titik agar sama persis dengan UI
    condensed_result = {
        "avg_blank": state.condense_spectrum(result["avg_blank"], n=15),
        "avg_reference": state.condense_spectrum(result["avg_reference"], n=15),
        "avg_sample": state.condense_spectrum(result["avg_sample"], n=15),
        "absorbance": state.condense_spectrum(result["absorbance"], n=15),
    }

    buf = exporter.export_absorbance_excel(condensed_result)

    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Hasil_Absorbansi.xlsx"'},
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
