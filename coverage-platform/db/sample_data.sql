-- 示例数据插入脚本
-- 用于测试覆盖率平台功能

USE coverage_db;

-- 插入示例覆盖率文件
INSERT INTO coverage_files (file_path, created_at, updated_at) VALUES
('tuna/models/user_repository.go', NOW(), NOW()),
('tuna/models/product.go', NOW(), NOW()),
('tuna/services/auth.go', NOW(), NOW());

-- 获取文件ID（假设ID为1, 2, 3）
SET @file1_id = LAST_INSERT_ID() - 2;
SET @file2_id = LAST_INSERT_ID() - 1;
SET @file3_id = LAST_INSERT_ID();

-- 为第一个文件插入覆盖率范围
INSERT INTO coverage_ranges (file_id, start_line, start_col, end_line, end_col, hit, created_at) VALUES
(@file1_id, 40, 2, 40, 26, 0, NOW()),
(@file1_id, 43, 54, 47, 2, 5, NOW()),
(@file1_id, 50, 1, 55, 10, 3, NOW()),
(@file1_id, 60, 1, 65, 5, 0, NOW()),
(@file1_id, 70, 1, 75, 20, 10, NOW());

-- 为第二个文件插入覆盖率范围
INSERT INTO coverage_ranges (file_id, start_line, start_col, end_line, end_col, hit, created_at) VALUES
(@file2_id, 10, 1, 15, 10, 2, NOW()),
(@file2_id, 20, 1, 25, 5, 0, NOW()),
(@file2_id, 30, 1, 35, 15, 8, NOW());

-- 为第三个文件插入覆盖率范围
INSERT INTO coverage_ranges (file_id, start_line, start_col, end_line, end_col, hit, created_at) VALUES
(@file3_id, 5, 1, 10, 20, 1, NOW()),
(@file3_id, 15, 1, 20, 10, 0, NOW()),
(@file3_id, 25, 1, 30, 5, 0, NOW()),
(@file3_id, 35, 1, 40, 15, 5, NOW()),
(@file3_id, 45, 1, 50, 10, 12, NOW()),
(@file3_id, 55, 1, 60, 8, 0, NOW());

