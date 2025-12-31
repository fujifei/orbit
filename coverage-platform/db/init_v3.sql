-- 创建数据库
CREATE DATABASE IF NOT EXISTS coverage_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE coverage_db;

-- 创建覆盖率报告表（存储上报的元数据）
CREATE TABLE IF NOT EXISTS coverage_reports (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    repo VARCHAR(500) NOT NULL COMMENT '仓库地址',
    repo_id VARCHAR(64) NOT NULL COMMENT '仓库唯一标识(SHA256)',
    branch VARCHAR(255) NOT NULL COMMENT '分支名',
    commit VARCHAR(100) NOT NULL COMMENT 'commit hash',
    ci_provider VARCHAR(50) COMMENT 'CI提供商',
    ci_pipeline_id VARCHAR(255) COMMENT 'Pipeline ID',
    ci_job_id VARCHAR(255) COMMENT 'Job ID',
    coverage_format VARCHAR(50) NOT NULL DEFAULT 'goc' COMMENT '覆盖率格式',
    coverage_raw TEXT NOT NULL COMMENT '原始覆盖率数据',
    status VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT '处理状态: pending, processing, completed, failed',
    error_message TEXT COMMENT '错误信息',
    created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳(毫秒)',
    INDEX idx_repo (repo(255)),
    INDEX idx_repo_id (repo_id),
    INDEX idx_branch (branch),
    INDEX idx_commit (commit),
    INDEX idx_status (status),
    INDEX idx_repo_branch_commit (repo(255), branch, commit),
    INDEX idx_repo_id_branch_commit (repo_id, branch, commit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率报告表';

-- 创建覆盖率文件表
CREATE TABLE IF NOT EXISTS coverage_files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    repo_id VARCHAR(64) NOT NULL COMMENT '仓库唯一标识',
    branch VARCHAR(255) NOT NULL COMMENT '分支名',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    updated_at BIGINT NOT NULL COMMENT '更新时间戳(毫秒)',
    INDEX idx_repo_id (repo_id),
    INDEX idx_branch (branch),
    INDEX idx_file_path (file_path(255)),
    INDEX idx_repo_id_branch (repo_id, branch),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率文件表';

-- 创建覆盖率范围表
CREATE TABLE IF NOT EXISTS coverage_ranges (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_id BIGINT NOT NULL COMMENT '文件ID',
    start_line INT NOT NULL COMMENT '起始行号',
    start_col INT NOT NULL COMMENT '起始列号',
    end_line INT NOT NULL COMMENT '结束行号',
    end_col INT NOT NULL COMMENT '结束列号',
    statements INT NOT NULL DEFAULT 0 COMMENT '该代码块包含的statement数',
    hit INT NOT NULL DEFAULT 0 COMMENT '执行次数(count)',
    created_at BIGINT NOT NULL COMMENT '创建时间戳(毫秒)',
    FOREIGN KEY (file_id) REFERENCES coverage_files(id) ON DELETE CASCADE,
    INDEX idx_file_id (file_id),
    INDEX idx_hit (hit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率范围表';

