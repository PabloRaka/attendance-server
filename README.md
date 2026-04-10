# 🚀 Modern Attendance System Backend (FastAPI)

Sistem Backend Absensi Modern menggunakan **FastAPI** dengan fitur **Face Recognition** (Pengenalan Wajah) yang dioptimalkan secara *asynchronous* dan penyimpanan database binary (**BYTEA**).

## ✨ Fitur Utama
- **Face Recognition**: Deteksi dan perbandingan wajah menggunakan OpenCV + Haar Cascade, hasil crop disimpan langsung di DB.
- **Async Processing**: Pemrosesan wajah dilakukan secara *non-blocking* menggunakan *worker threads* (`asyncio.to_thread`).
- **Database Storage**: Foto wajah disimpan sebagai binary (BLOB/BYTEA) sehingga tidak ada filesystem state yang harus disinkronkan.
- **OAuth2 + JWT**: Login memakai OAuth2 password flow dan token JWT yang dapat dikonfigurasi masa berlakunya (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **QR Challenge Flow**: Dashboard admin meminta token QR baru setiap 60 detik dan mobile client memverifikasi token itu untuk mencatat kehadiran.
- **Alembic Migrations**: Manajemen skema database yang profesional dan aman.
- **Dual Attendance**: Mendukung absensi via Face Recognition dan QR (legacy upload ataupun alur dashboard ↔ mobile).

---

## 🛠️ Persyaratan Sistem
- **Python 3.10+**
- **Virtual Environment** (`venv`)
- **OpenCV Dependencies** (libgl1-mesa-glx untuk Linux/Docker)

---

## ⚙️ Instalasi & Setup

### 1. Clone & Masuk ke Folder Backend
```bash
cd backend
```

### 2. Buat & Aktifkan Virtual Environment
**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```
**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependensi
```bash
pip install -r requirements.txt
```

---

## 🗄️ Database & Environment Setup

### 1. Konfigurasi `.env`
Salin file contoh `.env` dan sesuaikan dengan database Anda:
```bash
cp .env.example .env
```
Edit file `.env` dan tentukan dialek database Anda (**postgresql**, **mysql**, atau **sqlite**):
```env
DATABASE_DIALECT=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=uname
DB_PASSWORD=pwd
DB_NAME=absen
```

### 2. Jalankan Migrasi Database (Alembic)
Pastikan database Anda sudah ada, lalu terapkan skema terbaru:
```bash
alembic upgrade head
```

---

## 🚀 Menjalankan Aplikasi

Jalankan server pengembangan menggunakan **Uvicorn**:
```bash
uvicorn app.main:app --reload
```
Aplikasi akan berjalan di: `http://127.0.0.1:8000`

### 📖 Dokumentasi API
FastAPI menyediakan dokumentasi interaktif otomatis:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

## 🧩 Struktur Folder Utama
```text
backend/
├── alembic/            # Konfigurasi & file migrasi database
├── app/
│   ├── api/            # Dependency injection & logic per modul
│   ├── core/           # Konfigurasi aplikasi & settings
│   ├── database/       # SQLAlchemy engine & session setup
│   ├── models.py       # Definisi model database (SQLAlchemy)
│   ├── schemas/        # Validasi data (Pydantic)
│   └── main.py         # Entry point aplikasi & endpoint API
├── requirements.txt    # Daftar librari python
└── alembic.ini         # Konfigurasi utama Alembic
```

---

## 📚 Dokumentasi API
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`
- **Ringkasan manual**: lihat `doc/API.md` untuk alur lengkap endpoint (auth, face upload, QR challenge, endpoint admin).

---

## 🔐 Membuat Admin Pertama
Gunakan utilitas `app/utils/create_admin.py` setelah environment & migrasi siap:
```bash
cd backend
python3 app/utils/create_admin.py <username> <password> "<Full Name>"
```
Jika argumen tidak diberikan, script akan meminta input secara interaktif dan otomatis membuat/memperbarui user tersebut dengan role `admin`.

---

## ⚡ Tips Performa
- **Concurrency**: Sistem ini menggunakan threading untuk pemrosesan gambar agar server tidak *blocking* saat menghitung histogram wajah.
- **Binary Storage**: Foto disimpan langsung di tabel `users`. Hal ini mempercepat verifikasi karena tidak perlu operasi I/O file tambahan saat absensi.
- **QR Tokens**: Token dari `/api/attendance/token` hanya valid ±60 detik. Pastikan dashboard merefresh QR dan mobile client memanggil `/api/attendance/verify-token` segera setelah scan.

---

## ⚠️ Catatan Penting
Jika Anda berpindah dari sistem berbasis file lama, semua user perlu melakukan **Re-upload Foto Wajah** satu kali di halaman Profile agar data binary tersimpan di database yang baru.
