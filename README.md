# 🚀 Modern Attendance System Backend (FastAPI)

Backend absensi modern berbasis **FastAPI** dengan kombinasi **Face Recognition + QR Challenge**. Proses identifikasi wajah berjalan asynchronous, foto wajah disimpan sebagai binary di database, dan terdapat scheduler otomatis untuk melakukan auto check-out setiap malam.

**Frontend Repository**: [attendance-client](https://github.com/PabloRaka/attendance-client.git)

---

## ✨ Fitur Utama
- **Face Recognition Canggih**: Menggunakan kombinasi OpenCV YuNet (deteksi), SFace (embedding), dan MiniFASNetV2 (anti-spoofing/liveness) yang sudah disertakan di `app/assets/models`.
- **Anti-Spoofing & Threshold Dinamis**: Variabel `.env` `FACE_SIMILARITY_THRESHOLD` mengatur skor minimum (default 0.60). Laplacian blur check + model liveness mencegah foto layar.
- **Dual Attendance Flow**: Mendukung absensi via Face Recognition, QR (legacy upload), serta **QR challenge token** antara dashboard ↔ mobile.
- **OAuth2 + JWT**: Login memakai OAuth2 password flow + JWT dengan masa aktif configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Binary Storage**: Foto wajah disimpan langsung sebagai BLOB/BYTEA sehingga tidak perlu sinkronisasi filesystem.
- **Auto Check-Out**: `app/tasks.py` menjalankan background scheduler yang otomatis melakukan check-out pada pukul **23:00 WIB** untuk user yang belum keluar.
- **Alembic Migration**: Skema database terkelola dengan baik untuk SQLite/PostgreSQL/MySQL.

---

## 🧱 Stack & Arsitektur Singkat
- **FastAPI** + **Uvicorn** untuk HTTP server asynchronous.
- **SQLAlchemy 2.0** + Alembic untuk ORM & migrasi.
- **PostgreSQL / MySQL / SQLite** via konfigurasi `.env`.
- **OpenCV**, **NumPy**, **pyzbar** untuk face & QR processing.
- **python-jose**, **passlib** untuk otentikasi.
- Direktori utama: `app/api` (router), `app/services` (face pipeline), `app/core` (config), `app/utils` (helper), `app/tasks.py` (background job).

---

## 🧰 Prasyarat Sistem
- Python **3.10+** serta `pip` terbaru.
- Disarankan virtual environment (`python -m venv .venv`).
- Library sistem untuk multimedia:
  - Linux: `sudo apt install libgl1-mesa-glx libglib2.0-0 libzbar0`
  - macOS: `brew install opencv zbar`
  - Windows: gunakan package resmi OpenCV & ZBar (tersedia via pip/installer).
- Model ONNX sudah ada di `app/assets/models`. Jika hilang, unduh ulang file berikut:
  - `face_detection_yunet_2023mar.onnx`
  - `face_recognition_sface_2021dec.onnx`
  - `MiniFASNetV2.onnx`

---

## ⚡ Quick Start Pengembangan Lokal
1. Masuk folder backend:
   ```bash
   cd backend
   ```
2. Buat & aktifkan virtual env:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
3. Install dependency:
   ```bash
   pip install -r requirements.txt
   ```
4. Siapkan konfigurasi environment (lihat bagian berikut), jalankan migrasi, lalu start server.

---

## 🔐 Konfigurasi Environment (`.env`)
Salin contoh dan sesuaikan:
```bash
cp .env.example .env
```

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `DATABASE_URL` | kosong | SQLAlchemy URL lengkap (override semua isian DB_*). |
| `DATABASE_DIALECT` | `sqlite` | `sqlite`, `postgres`, atau `mysql`. Menentukan driver default. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `localhost:5432` dll | Diambil ketika `DATABASE_URL` kosong. |
| `SQLITE_PATH` | `./attendance.db` | Lokasi file SQLite jika memakai `sqlite`. |
| `SECRET_KEY` | `change-me` | Key untuk JWT signing. Ganti di production. |
| `ALGORITHM` | `HS256` | Algoritma JWT. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Masa berlaku token (menit). |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | CSV origins untuk CORS FastAPI. |
| `FACE_SIMILARITY_THRESHOLD` | `0.60` | Skor minimum face match. |

> **Tips**: Untuk PostgreSQL gunakan driver `psycopg2-binary`, sedangkan MySQL memakai `PyMySQL`. Pastikan DB driver yang diperlukan sudah ter-install.

---

## 🗄️ Database & Migrasi
- Default pengembangan memakai SQLite (`attendance.db` di root backend).
- Untuk PostgreSQL/MySQL, pastikan database sudah dibuat dan kredensial sesuai di `.env`.
- Terapkan migrasi terbaru:
  ```bash
  alembic upgrade head
  ```
- Menambahkan migrasi baru:
  ```bash
  alembic revision -m "Add something" --autogenerate
  alembic upgrade head
  ```

---

## 🚀 Menjalankan Aplikasi
```bash
uvicorn app.main:app --reload
```
Server default di `http://127.0.0.1:8000`.

- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

FastAPI event `startup` otomatis menjalankan `scheduler_loop()` sehingga auto check-out berjalan tanpa konfigurasi tambahan. Pastikan timezone server sesuai atau gunakan container/VM dengan zona **Asia/Jakarta (UTC+7)** agar penjadwalan 23:00 WIB akurat.

---

## 🔧 Utilitas Operasional
- **Buat Admin Pertama**
  ```bash
  cd backend
  python app/utils/create_admin.py
  or 
  python app/utils/create_admin.py <username> <password> "Full Name"
  ```
  Jika argumen kosong script akan meminta input interaktif dan membuat/replace user role `admin`.
- **Reset Face Photo Pengguna**: Admin dapat menghapus/mengunggah ulang via endpoint `/api/admin/user/{id}/face` jika hasil verifikasi kurang konsisten.
- **Logika Auto Check-Out**: Cron internal akan membuat record `method=system_auto` dan `status=auto` untuk user yang masih `in` saat 23:00 WIB. Riwayat dapat dilihat dari log admin.

---

## 🧩 Struktur Folder
```text
backend/
├── alembic/             # Skrip migrasi database
├── app/
│   ├── api/             # Router FastAPI (auth, attendance, admin, user)
│   ├── assets/models/   # Model ONNX YuNet, SFace, MiniFASNet
│   ├── core/            # Settings + konfigurasi aplikasi
│   ├── database/        # Engine, SessionLocal, dependency DB
│   ├── services/        # Face pipeline & utilitas QR
│   ├── tasks.py         # Background scheduler auto checkout
│   ├── utils/           # Helper (auth hashing, scripts)
│   └── main.py          # Entry point FastAPI
├── doc/API.md           # Dokumentasi endpoint detail
├── requirements.txt     # Dependency Python
└── attendance.db        # SQLite default (opsional)
```

---

## 🧠 Pipeline Face Recognition (Ringkasan)
1. **Upload** wajah (`/api/user/upload-face`) → file di-decode OpenCV, dipotong, lalu hasil crop disimpan sebagai binary BLOB.
2. **Attendance Face** (`/api/attendance/face`) → request dialihkan ke thread worker (`asyncio.to_thread`), lalu dihitung embedding + similarity terhadap referensi user.
3. **Liveness & Anti-Spoofing**: Laplacian blur + MiniFASNet wajib lolos sebelum pencocokan dianggap valid.
4. **Skor Similarity**: Jika skor >= `FACE_SIMILARITY_THRESHOLD`, sistem otomatis toggle `attendance_type` (`in`/`out`).

Pipeline penuh dapat dilihat di `app/services/face_service.py`.

---

## 📚 Dokumentasi API
- Swagger & ReDoc seperti di atas.
- **Manual Lengkap**: `doc/API.md` merinci payload, response, dan contoh error untuk seluruh endpoint (auth, attendance, admin, user).

---

## ❗ Troubleshooting Cepat
- **`ImportError: libGL.so.1`** → Pastikan `libgl1-mesa-glx` (Linux) sudah ter-install.
- **`Cannot find zbar shared library`** → Install `libzbar0` (Linux) atau `brew install zbar` (macOS) agar QR scan berfungsi.
- **`FileNotFoundError: ...onnx`** → Pastikan direktori `app/assets/models` berisi ketiga model ONNX. Unduh ulang jika perlu.
- **Gagal Face Match** → Periksa `FACE_SIMILARITY_THRESHOLD` terlalu tinggi atau user belum upload foto.
- **Token QR Expired** → Token dari `/api/attendance/token` hanya hidup ±60 detik, jadi frontend wajib refresh otomatis.

---

Backend siap digunakan! Jika menambah fitur baru, mohon update README serta dokumentasi `doc/API.md` agar tetap sinkron.
