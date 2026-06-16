# Webcam Spectrophotometer — Real-time Optical Analysis

Aplikasi spektrofotometer berbasis web menggunakan kamera webcam sebagai sensor intensitas cahaya. Aplikasi ini dirancang untuk mengukur spektrum intensitas cahaya dan absorbansi (A) secara real-time dari larutan sampel dengan melakukan serangkaian percobaan (9 kali ulangan).

---

## Fitur Utama

- **Live Sensor Feed**: Streaming video webcam secara real-time disertai pelacakan spektrum warna dan intensitas.
- **Pendeteksi Warna Dominan**: Mengenali dan menampilkan warna dominan yang sedang ditangkap berdasarkan panjang gelombang cahaya.
- **Kalibrasi Gelap (Set 0)**: Tombol khusus untuk menetapkan titik 0 (nol) intensitas cahaya saat kondisi gelap untuk akurasi data.
- **Dukungan Multi-Kamera**: Memiliki kapabilitas pendeteksi dan perpindahan kamera secara dinamis dari antarmuka (memprioritaskan kamera eksternal secara otomatis).
- **Modular Experiment Flow**: Panduan terintegrasi untuk melakukan 9 tahap percobaan:
  1. **Kuvet Kosong** (3 kali ulangan) — Baseline correction.
  2. **Aquadest / $I_0$** (3 kali ulangan) — Intensitas referensi.
  3. **Larutan Pewarna Makanan / $I$** (3 kali ulangan) — Intensitas sampel.
- **Interactive UI & Custom Modals**: Tampilan tema gelap premium (_Glassmorphism_) lengkap dengan peringatan dialog kustom (tanpa alert/confirm bawaan peramban).
- **Eksport Data & Hasil Visual**:
  - Menyimpan tangkapan gambar per percobaan (bisa diunduh).
  - Ekspor data spektrum tiap percobaan individual ke Excel (`.xlsx`).
  - Ekspor hasil grafik analisis absorbansi lengkap rata-rata kelompok ke Excel (`.xlsx`).
  - Grafik spektrum yang dilengkapi keterangan sumbu (X dan Y) serta detail koordinat (_tooltip_).

---

## Struktur Proyek (Modular)

Proyek ini telah direfaktor menjadi beberapa modul terpisah untuk kemudahan pemeliharaan:

```text
spektrofotometer/
│
├── app/
│   ├── app.py           # Entry point utama FastAPI server & router.
│   ├── config.py        # Konstanta konfigurasi percobaan & path sistem.
│   ├── state.py         # Pengelola state global aplikasi & logika matematika absorbansi.
│   ├── camera.py        # Pengendali webcam (OpenCV), algoritma deteksi warna dominan & kalkulasi LUX.
│   ├── exporter.py      # Pengelola pembuatan dokumen laporan Excel (openpyxl).
│   │
│   ├── static/          # Aset statis web (CSS Tema Gelap Premium, JS Grafik interaktif).
│   ├── templates/       # Template HTML struktur antarmuka (Jinja2).
│   └── captures/        # Folder tempat penyimpanan gambar `.jpg` hasil tangkapan percobaan.
│
├── requirements.txt     # Daftar pustaka / library Python yang dibutuhkan.
└── README.md            # Dokumentasi panduan penggunaan proyek.
```

---

## Persyaratan Sistem & Instalasi

### 1. Prasyarat
Pastikan sistem Anda sudah terinstal **Python 3.8+** dan kamera webcam eksternal terhubung di port USB.

### 2. Instalasi Dependensi
Buka terminal/command prompt pada direktori utama proyek (`spektrofotometer/`) lalu jalankan perintah berikut:

```bash
pip install -r requirements.txt
```

---

## Cara Menjalankan Aplikasi

Jalankan perintah berikut pada direktori utama proyek (`spektrofotometer/`):

```bash
python app/app.py
```

Setelah server aktif, buka web browser Anda dan akses alamat berikut:
```text
http://localhost:8000/
```

---

## Alur Percobaan di Dashboard

1. **Kalibrasi Gelap**: Matikan sumber cahaya atau letakkan sistem dalam kondisi tertutup gelap total. Tekan tombol **Set 0** agar intensitas sisa dikurangi menjadi nol.
2. **Kamera**: Pastikan kamera yang digunakan sudah tepat dengan menekan modul penampil nama kamera di kiri atas layar panel (bisa berpindah antar kamera).
3. **Kuvet Kosong**: Tempatkan kuvet kosong pada spektrofotometer, lalu tekan tombol **Mulai Percobaan** untuk merekam data. Ulangi proses hingga 3 kali percobaan untuk _baseline_.
4. **Referensi & Sampel**: Lanjutkan proses perekaman yang sama untuk kelompok **Aquadest ($I_0$)** (3 kali) dan kelompok **Larutan Pewarna Makanan ($I$)** (3 kali).
5. **Analisis Absorbansi**: Setelah total 9 percobaan selesai, gulir layar ke paling bawah. Terdapat hasil kurva Absorbansi (A) lengkap beserta fungsi eksport berkas data analisis Excel.
6. **Reset**: Gunakan tombol **Reset Ulang** untuk mengosongkan seluruh data sekaligus gambar dari _storage_ untuk siap melakukan pengujian baru.
