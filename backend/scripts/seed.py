"""Tạo tài khoản có sẵn + 1 vụ án mẫu. Chạy lại nhiều lần không tạo trùng.

Chạy (từ gốc repo): venv\\Scripts\\python.exe backend/scripts/seed.py
Thêm --demo: tạo vài lần lưu chứng cứ mẫu của duongsu, bidon để màn hình có dữ liệu xem
(chỉ tạo khi họ chưa có biên nhận nào; file mẫu lưu ở backend/scripts/demo_files/ để thư ký chọn lại khi đối chiếu).
"""
import io
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.enums import CaseRole, UserRole
from app.db.models import CaseParticipant, CourtCase, User
from app.db.session import SessionLocal

COURT = "TAND Quận 1, TP.HCM"
APPEAL_COURT = "TAND TP.HCM"

# (tên đăng nhập, mật khẩu, họ tên, vai trò, tòa)
USERS = [
    ("duongsu", "1234", "Nguyễn Văn An", UserRole.PARTY, None),
    ("thuky", "5678", "Lê Thị Thư Ký", UserRole.CLERK, COURT),
    # Tài khoản phụ để test đủ các vai trong quy trình
    ("bidon", "1234", "Trần Thị Bình", UserRole.PARTY, None),
    ("luatsu", "1234", "Hoàng Luật Sư", UserRole.PARTY, None),
    ("thamphan", "5678", "Võ Minh Thẩm", UserRole.JUDGE, COURT),
    ("thuky.phuctham", "5678", "Phạm Văn Phúc", UserRole.CLERK, APPEAL_COURT),
    ("admin", "5678", "Quản trị viên", UserRole.ADMIN, COURT),
]

CASE_NUMBER = "01/2026/DS-ST"
CASE_PARTICIPANTS = [
    ("thuky", CaseRole.CLERK),
    ("thamphan", CaseRole.JUDGE),
    ("duongsu", CaseRole.PLAINTIFF),
    ("bidon", CaseRole.DEFENDANT),
    ("luatsu", CaseRole.LAWYER),
]


DEMO_DIR = Path(__file__).resolve().parent / "demo_files"
# (người lưu, các file): nội dung có đầu file đúng định dạng để qua kiểm tra loại file
DEMO_RECEIPTS = [
    ("duongsu", [("hop_dong_vay.pdf", b"%PDF-1.7\n"), ("anh_chuyen_khoan.jpg", b"\xff\xd8\xff\xe0"),
                 ("ghi_am_cuoc_goi.m4a", b"\x00\x00\x00\x20ftypM4A ")]),
    ("duongsu", [("tin_nhan_zalo.png", b"\x89PNG\r\n\x1a\n"), ("video_cuoc_hop.mp4", b"\x00\x00\x00\x18ftypmp42")]),
    ("bidon", [("giay_vay_tien.jpg", b"\xff\xd8\xff\xe0")]),
]


def seed_demo_receipts(db) -> None:
    from app.db.enums import SubmissionType
    from app.db.models import Submission
    from app.services.submission_service import create_self_submission

    DEMO_DIR.mkdir(exist_ok=True)
    users = {u: db.scalar(select(User).where(User.username == u)) for u, _ in DEMO_RECEIPTS}
    # Ai đã có biên nhận (chạy --demo lần 2, hoặc đã tự lưu chứng trên giao diện) thì không tạo mẫu cho người đó
    has_receipts = {u for u, user in users.items() if db.scalar(select(Submission.id).where(
        Submission.owner_id == user.id, Submission.type == SubmissionType.SELF))}
    for username, files in DEMO_RECEIPTS:
        user = users[username]
        if username in has_receipts:
            continue
        items = []
        for name, header in files:
            path = DEMO_DIR / name
            if not path.exists():
                path.write_bytes(header + os.urandom(20_000))
            items.append((name, io.BytesIO(path.read_bytes())))
        submission = create_self_submission(db, user, items)  # nghỉ 1–3 giây giữa các file như lưu chứng thật
        print(f"+ biên nhận {submission.receipt_code} của {username}: {', '.join(n for n, _ in files)}")
    print(f"  File mẫu (để thư ký chọn lại khi đối chiếu): {DEMO_DIR}")


def main():
    with SessionLocal() as db:
        users = {}
        for username, password, name, role, court in USERS:
            user = db.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(username=username, email=f"{username}@evidencechain.test", full_name=name, role=role,
                            court_name=court, password_hash=hash_password(password))
                db.add(user)
                print(f"+ {role.value:5} {username} / {password}")
            else:
                print(f"= {role.value:5} {username} (đã có)")
            users[username] = user
        db.flush()

        case = db.scalar(select(CourtCase).where(CourtCase.case_number == CASE_NUMBER))
        if case is None:
            case = CourtCase(case_number=CASE_NUMBER, title="Tranh chấp hợp đồng mua bán hàng hóa",
                             court_name=COURT, created_by=users["thuky"].id)
            db.add(case)
            db.flush()
            print(f"+ vụ án {CASE_NUMBER}")
        for username, role in CASE_PARTICIPANTS:
            exists = db.scalar(select(CaseParticipant).where(
                CaseParticipant.case_id == case.id, CaseParticipant.user_id == users[username].id,
                CaseParticipant.role_in_case == role))
            if exists is None:
                db.add(CaseParticipant(case_id=case.id, user_id=users[username].id, role_in_case=role))
        db.commit()
        if "--demo" in sys.argv:
            seed_demo_receipts(db)
    print("Xong.")


if __name__ == "__main__":
    main()
