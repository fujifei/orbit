-- 创建数据库
CREATE DATABASE IF NOT EXISTS coverage_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE coverage_db;

-- 创建覆盖率报告表（存储上报的元数据）
CREATE TABLE IF NOT EXISTS coverage_reports (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    repo VARCHAR(500) NOT NULL COMMENT '仓库地址',
    branch VARCHAR(255) NOT NULL COMMENT '分支名',
    commit VARCHAR(100) NOT NULL COMMENT 'commit hash',
    ci_provider VARCHAR(50) COMMENT 'CI提供商',
    ci_pipeline_id VARCHAR(255) COMMENT 'Pipeline ID',
    ci_job_id VARCHAR(255) COMMENT 'Job ID',
    coverage_format VARCHAR(50) NOT NULL DEFAULT 'goc' COMMENT '覆盖率格式',
    coverage_raw TEXT NOT NULL COMMENT '原始覆盖率数据',
    timestamp BIGINT NOT NULL COMMENT '上报时间戳',
    status VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT '处理状态: pending, processing, completed, failed',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_repo (repo(255)),
    INDEX idx_branch (branch),
    INDEX idx_commit (commit),
    INDEX idx_timestamp (timestamp),
    INDEX idx_status (status),
    INDEX idx_repo_branch_commit (repo(255), branch, commit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率报告表';

-- 修改覆盖率文件表（添加报告ID字段）
-- 先添加允许 NULL 的字段，避免已有数据导致外键约束错误
ALTER TABLE coverage_files 
    ADD COLUMN report_id BIGINT NULL COMMENT '报告ID' AFTER id;

-- 添加索引
ALTER TABLE coverage_files 
    ADD INDEX idx_report_id (report_id);

-- 添加外键约束（如果表中已有数据，需要先更新 report_id 后再执行此步骤）
-- 注意：如果 coverage_files 表中有数据但 report_id 为 NULL，需要先更新数据后再添加外键约束
-- ALTER TABLE coverage_files 
--     ADD CONSTRAINT fk_coverage_files_report_id 
--         FOREIGN KEY (report_id) REFERENCES coverage_reports(id) ON DELETE CASCADE;

-- 注意：coverage_ranges 表结构未变化，无需修改

