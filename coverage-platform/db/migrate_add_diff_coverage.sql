-- 增量覆盖率功能迁移脚本
-- 为 coverage_reports 表添加基准 commit 和配置相关字段

USE coverage_db;

-- 添加基准分支和基准 commit 字段
ALTER TABLE coverage_reports 
ADD COLUMN base_branch VARCHAR(255) DEFAULT 'master' COMMENT '基准分支' AFTER branch,
ADD COLUMN base_commit VARCHAR(100) DEFAULT '' COMMENT '基准 commit hash' AFTER commit;

-- 添加索引
ALTER TABLE coverage_reports 
ADD INDEX idx_base_branch (base_branch),
ADD INDEX idx_base_commit (base_commit);

-- 创建配置表（用于存储各个仓库的基准分支配置）
CREATE TABLE IF NOT EXISTS coverage_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    repo_id VARCHAR(64) NOT NULL COMMENT '仓库唯一标识',
    base_branch VARCHAR(255) NOT NULL DEFAULT 'master' COMMENT '基准分支',
    created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳(毫秒)',
    UNIQUE KEY uk_repo_id (repo_id),
    INDEX idx_base_branch (base_branch)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率配置表';

