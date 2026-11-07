-- Chạy 1 lần khi container PostgreSQL tạo dữ liệu mới.
-- evidence_app: tài khoản ứng dụng dùng. Quyền trên từng bảng do migration cấp
-- (chỉ SELECT, INSERT trên bảng chỉ ghi thêm — F6).
CREATE ROLE evidence_app LOGIN PASSWORD 'app_dev_pw';
GRANT CONNECT ON DATABASE evidencechain TO evidence_app;
GRANT USAGE ON SCHEMA public TO evidence_app;
