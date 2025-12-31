-- 扩展覆盖率配置表和修改覆盖率报告表
-- 迁移脚本：添加仓库名称、链接、排除目录、排除文件后缀字段

USE coverage_db;

-- 1. 扩展 coverage_config 表
-- 添加仓库名称字段
ALTER TABLE coverage_config 
ADD COLUMN repo_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '仓库名称（从仓库链接提取）' AFTER repo_id;

-- 添加仓库链接字段
ALTER TABLE coverage_config 
ADD COLUMN repo_url VARCHAR(500) NOT NULL DEFAULT '' COMMENT '仓库链接（如https://github.com/fujifei/tuna.git）' AFTER repo_name;

-- 添加排除目录字段
ALTER TABLE coverage_config 
ADD COLUMN exclude_dirs TEXT COMMENT '覆盖率统计排除目录，多个用分号分隔（如cmd/;config/）' AFTER base_branch;

-- 添加排除文件后缀字段
ALTER TABLE coverage_config 
ADD COLUMN exclude_files TEXT COMMENT '覆盖率统计排除文件后缀，多个用分号分隔（如*._test.go;active_test.go）' AFTER exclude_dirs;

-- 添加索引
ALTER TABLE coverage_config ADD INDEX idx_repo_name (repo_name);

-- 2. 修改 coverage_reports 表
-- 添加 repo_name 字段（如果不存在）
ALTER TABLE coverage_reports 
ADD COLUMN IF NOT EXISTS repo_name VARCHAR(255) NOT NULL DEFAULT '' COMMENT '仓库名称' AFTER repo_id;

-- 添加索引
ALTER TABLE coverage_reports ADD INDEX IF NOT EXISTS idx_repo_name (repo_name);

-- 注意：repo_name 字段用于快速搜索和展示
-- repo 字段（仓库链接）可以移除，通过 repo_id 从 coverage_config 表查询

