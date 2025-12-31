-- 从 coverage_reports 表移除 repo 字段
-- repo_name 保留，方便列表搜索
-- repo_url 可以通过 repo_id 从 coverage_config 表实时查询

USE coverage_db;

-- 移除 repo 字段及其索引
ALTER TABLE coverage_reports DROP INDEX idx_repo;
ALTER TABLE coverage_reports DROP COLUMN repo;

-- 注意：repo_name 字段保留，用于快速搜索和展示

