-- Migration script from v2 to v3
-- 迁移脚本：从v2迁移到v3

USE coverage_db;

-- 1. 修改 coverage_reports 表

-- 添加 repo_id 字段
ALTER TABLE coverage_reports 
    ADD COLUMN repo_id VARCHAR(64) NOT NULL DEFAULT '' COMMENT '仓库唯一标识(SHA256)' AFTER repo;

-- 删除 timestamp 字段（先备份数据到新字段，如果需要的话）
-- 注意：如果 timestamp 字段有数据需要保留，先迁移到 created_at
-- UPDATE coverage_reports SET created_at = timestamp WHERE timestamp > 0;

-- 删除 timestamp 字段及其索引
DROP INDEX idx_timestamp ON coverage_reports;
ALTER TABLE coverage_reports DROP COLUMN timestamp;

-- 修改 created_at 和 updated_at 为 BIGINT 类型
-- 注意：需要先将现有的 TIMESTAMP 转换为 BIGINT (毫秒时间戳)
ALTER TABLE coverage_reports 
    MODIFY COLUMN created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    MODIFY COLUMN updated_at BIGINT NOT NULL COMMENT '更新时间戳(毫秒)';

-- 添加新索引
ALTER TABLE coverage_reports ADD INDEX idx_repo_id (repo_id);
ALTER TABLE coverage_reports ADD INDEX idx_repo_id_branch_commit (repo_id, branch, commit);

-- 2. 修改 coverage_files 表

-- 删除 report_id 的外键约束（如果存在）
-- ALTER TABLE coverage_files DROP FOREIGN KEY fk_coverage_files_report_id;

-- 删除 report_id 的索引
DROP INDEX idx_report_id ON coverage_files;

-- 将 report_id 改名为 repo_id 并修改类型
ALTER TABLE coverage_files 
    CHANGE COLUMN report_id repo_id VARCHAR(64) NOT NULL COMMENT '仓库唯一标识';

-- 添加 branch 字段
ALTER TABLE coverage_files 
    ADD COLUMN branch VARCHAR(255) NOT NULL DEFAULT '' COMMENT '分支名' AFTER repo_id;

-- 修改 created_at 和 updated_at 为 BIGINT 类型
ALTER TABLE coverage_files 
    MODIFY COLUMN created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    MODIFY COLUMN updated_at BIGINT NOT NULL COMMENT '更新时间戳(毫秒)';

-- 添加新索引
ALTER TABLE coverage_files ADD INDEX idx_repo_id (repo_id);
ALTER TABLE coverage_files ADD INDEX idx_branch (branch);
ALTER TABLE coverage_files ADD INDEX idx_repo_id_branch (repo_id, branch);

-- 3. 修改 coverage_ranges 表

-- 修改 created_at 为 BIGINT 类型
ALTER TABLE coverage_ranges 
    MODIFY COLUMN created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)';

-- 注意事项：
-- 1. 执行此脚本前请先备份数据库
-- 2. repo_id 字段需要通过应用程序填充，可以使用 repo URL 的 SHA256 hash
-- 3. coverage_files 的 branch 字段需要从对应的 coverage_reports 中填充
-- 4. 时间戳字段的转换需要在应用程序层面处理

