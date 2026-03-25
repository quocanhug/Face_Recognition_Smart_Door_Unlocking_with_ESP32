"""
=============================================================
 MIGRATE PKL → SQLite
=============================================================
 Chuyển dữ liệu từ cv/user_database.pkl sang SQLite.
 Chạy 1 lần: python migrate_pkl.py
=============================================================
"""

import os
import sys
import pickle
import numpy as np

# Add paths so pickle can find UserInfo class
_here = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_here))
_cv_dir = os.path.join(_project_root, "cv")
sys.path.insert(0, _here)
sys.path.insert(0, _cv_dir)

from database import engine, SessionLocal
from models import Base, User, FaceEmbedding


def migrate():
    # Tìm file pkl
    cv_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "cv"
    )
    pkl_path = os.path.join(cv_dir, "user_database.pkl")

    if not os.path.exists(pkl_path):
        print(f"[MIGRATE] ❌ Không tìm thấy: {pkl_path}")
        return

    # Load pkl
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)

    users = data.get('users', {})
    print(f"[MIGRATE] Tìm thấy {len(users)} users trong pkl")

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        migrated_users = 0
        migrated_embs = 0

        for old_id, old_user in users.items():
            # Check duplicate
            existing = db.query(User).filter(
                User.mssv == old_user.mssv
            ).first()
            if existing:
                print(f"  [SKIP] {old_user.ho_ten} ({old_user.mssv}) - đã tồn tại")
                continue

            # Create user
            user = User(name=old_user.ho_ten, mssv=old_user.mssv)
            db.add(user)
            db.flush()  # Get ID

            # Add embeddings
            for emb in old_user.embeddings:
                fe = FaceEmbedding(
                    user_id=user.id,
                    embedding=FaceEmbedding.from_vector(emb)
                )
                db.add(fe)
                migrated_embs += 1

            migrated_users += 1
            print(f"  [OK] {old_user.ho_ten} ({old_user.mssv}) → "
                  f"{len(old_user.embeddings)} embeddings")

        db.commit()

        print(f"\n{'='*45}")
        print(f"  ✅ MIGRATION HOÀN TẤT")
        print(f"  Users: {migrated_users}")
        print(f"  Embeddings: {migrated_embs}")
        print(f"{'='*45}")

    except Exception as e:
        db.rollback()
        print(f"[MIGRATE] ❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
