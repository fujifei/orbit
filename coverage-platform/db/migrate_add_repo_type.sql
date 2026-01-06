-- 为 coverage_config 表添加 repo_type 字段
-- 迁移脚本：添加仓库类型字段（1=go, 2=python, 3=java）

USE coverage_db;

-- 添加仓库类型字段
ALTER TABLE coverage_config 
ADD COLUMN repo_type INT NOT NULL DEFAULT 1 COMMENT '仓库类型：1=go语言，2=python语言，3=java语言' AFTER repo_url;

-- 添加索引
ALTER TABLE coverage_config ADD INDEX idx_repo_type (repo_type);

