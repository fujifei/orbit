-- ============================================
-- 覆盖率平台数据库初始化脚本
-- ============================================
-- 说明：此脚本用于初始化覆盖率平台的MySQL数据库
-- 包括创建数据库和所有表结构
-- ============================================

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- ============================================
-- 1. 创建数据库
-- ============================================
CREATE DATABASE IF NOT EXISTS `coverage_db` 
    DEFAULT CHARACTER SET utf8mb4 
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE `coverage_db`;

-- ============================================
-- 1.1 创建用户并授权（允许从Docker网络连接）
-- ============================================
-- 注意：MySQL 8.0通过环境变量会自动创建用户，但可能只允许从localhost连接
-- 这里显式创建用户并授权允许从任何主机（%）连接，以便Docker容器可以访问
-- 使用CREATE USER IF NOT EXISTS（MySQL 8.0.11+支持）
-- 如果使用较旧版本，可以注释掉CREATE USER行，只保留GRANT语句
CREATE USER IF NOT EXISTS 'coverage'@'%' IDENTIFIED BY 'coverage123';
GRANT ALL PRIVILEGES ON `coverage_db`.* TO 'coverage'@'%';
-- 同时确保localhost用户也有权限（如果环境变量创建了该用户）
GRANT ALL PRIVILEGES ON `coverage_db`.* TO 'coverage'@'localhost';
FLUSH PRIVILEGES;

-- ============================================
-- 2. 创建表结构
-- ============================================

-- 2.1 覆盖率报告表 (coverage_reports)
CREATE TABLE IF NOT EXISTS `coverage_reports` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `repo_id` VARCHAR(64) NOT NULL COMMENT '仓库唯一标识',
    `repo_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '仓库名称',
    `branch` VARCHAR(255) NOT NULL COMMENT '分支名称',
    `base_branch` VARCHAR(255) DEFAULT 'master' COMMENT '基准分支',
    `commit` VARCHAR(100) NOT NULL COMMENT '提交哈希',
    `base_commit` VARCHAR(100) DEFAULT '' COMMENT '基准提交哈希',
    `ci_provider` VARCHAR(50) DEFAULT NULL COMMENT 'CI提供商',
    `ci_pipeline_id` VARCHAR(255) DEFAULT NULL COMMENT 'CI流水线ID',
    `ci_job_id` VARCHAR(255) DEFAULT NULL COMMENT 'CI任务ID',
    `coverage_format` VARCHAR(50) NOT NULL DEFAULT 'goc' COMMENT '覆盖率格式',
    `coverage_raw` TEXT DEFAULT NULL COMMENT '原始覆盖率数据',
    `status` VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT '状态',
    `error_message` TEXT DEFAULT NULL COMMENT '错误信息',
    `created_at` BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    `updated_at` BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    PRIMARY KEY (`id`),
    INDEX `idx_repo_id` (`repo_id`),
    INDEX `idx_repo_name` (`repo_name`),
    INDEX `idx_branch` (`branch`),
    INDEX `idx_commit` (`commit`),
    INDEX `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率报告表';

-- 2.2 覆盖率文件表 (coverage_files)
CREATE TABLE IF NOT EXISTS `coverage_files` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `repo_id` VARCHAR(64) NOT NULL COMMENT '仓库唯一标识',
    `branch` VARCHAR(255) NOT NULL COMMENT '分支名称',
    `file_path` VARCHAR(500) NOT NULL COMMENT '文件路径',
    `created_at` BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    `updated_at` BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    PRIMARY KEY (`id`),
    INDEX `idx_repo_id` (`repo_id`),
    INDEX `idx_branch` (`branch`),
    INDEX `idx_file_path` (`file_path`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率文件表';

-- 2.3 覆盖率范围表 (coverage_ranges)
CREATE TABLE IF NOT EXISTS `coverage_ranges` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `file_id` INT NOT NULL COMMENT '文件ID（关联coverage_files.id）',
    `start_line` INT NOT NULL COMMENT '起始行号',
    `start_col` INT NOT NULL COMMENT '起始列号',
    `end_line` INT NOT NULL COMMENT '结束行号',
    `end_col` INT NOT NULL COMMENT '结束列号',
    `statements` INT NOT NULL DEFAULT 0 COMMENT '该代码块包含的语句数',
    `hit` INT NOT NULL DEFAULT 0 COMMENT '执行次数（覆盖的行，hit>0；未覆盖的行，hit=0）',
    `created_at` BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    PRIMARY KEY (`id`),
    INDEX `idx_file_id` (`file_id`),
    INDEX `idx_hit` (`hit`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率范围表';

-- 2.4 配置表 (coverage_config)
CREATE TABLE IF NOT EXISTS `coverage_config` (
    `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `repo_id` VARCHAR(64) NOT NULL COMMENT '仓库唯一标识',
    `repo_name` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '仓库名称',
    `repo_url` VARCHAR(500) NOT NULL DEFAULT '' COMMENT '仓库链接',
    `repo_type` INT NOT NULL DEFAULT 1 COMMENT '仓库类型：1=go, 2=python, 3=java',
    `base_branch` VARCHAR(255) NOT NULL DEFAULT 'master' COMMENT '基准分支',
    `exclude_dirs` TEXT DEFAULT NULL COMMENT '排除目录（分号分隔）',
    `exclude_files` TEXT DEFAULT NULL COMMENT '排除文件后缀（分号分隔）',
    `created_at` BIGINT NOT NULL COMMENT '创建时间戳（毫秒）',
    `updated_at` BIGINT NOT NULL COMMENT '更新时间戳（毫秒）',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_repo_id` (`repo_id`),
    INDEX `idx_repo_name` (`repo_name`),
    INDEX `idx_repo_type` (`repo_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率配置表';

-- ============================================
-- 3. 创建外键约束（可选，根据实际需求）
-- ============================================
-- 注意：如果启用外键约束，删除文件时需要先删除相关的ranges记录
-- ALTER TABLE `coverage_ranges` 
--     ADD CONSTRAINT `fk_coverage_ranges_file_id` 
--     FOREIGN KEY (`file_id`) 
--     REFERENCES `coverage_files` (`id`) 
--     ON DELETE CASCADE 
--     ON UPDATE CASCADE;

-- ============================================
-- 初始化完成
-- ============================================
SELECT 'Database and tables initialized successfully!' AS message;

