import os
import sys
import asyncio
import numpy as np
from sqlalchemy.orm import Session

# Add the parent directory to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app import models
from app.database import SessionLocal
from app.services import face_service

async def migrate():
    print("Memulai migrasi embedding wajah...")
    db: Session = SessionLocal()
    try:
        # Cari user yang punya foto tapi belum punya embedding
        users = db.query(models.User).filter(
            models.User.face_image != None,
            models.User.face_embedding == None
        ).all()
        
        if not users:
            print("✅ Semua user sudah memiliki embedding. Tidak ada yang perlu dimigrasi.")
            return

        print(f"📦 Ditemukan {len(users)} user yang butuh migrasi.")
        
        count = 0
        for user in users:
            print(f"🔄 Memproses user: {user.username}...", end="", flush=True)
            try:
                # Ekstrak embedding (menggunakan fungsi sync agar simpel di loop ini)
                # Tapi kita pakai async wrapper agar konsisten dengan load model
                feat_bytes = await face_service.async_extract_embedding(user.face_image)
                
                if feat_bytes:
                    user.face_embedding = feat_bytes
                    db.commit()
                    count += 1
                    print(" [DONE]")
                else:
                    print(" [FAILED - Wajah tidak terdeteksi]")
            except Exception as e:
                print(f" [ERROR - {str(e)}]")
        
        print(f"\n✨ Migrasi selesai! {count}/{len(users)} user berhasil diperbarui.")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
