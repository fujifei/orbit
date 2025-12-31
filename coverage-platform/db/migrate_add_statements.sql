-- 迁移脚本：为 coverage_ranges 表添加 statements 字段
-- 执行时间：2025-12-30
-- 说明：修复覆盖率计算bug，添加statements字段用于正确计算覆盖率

USE coverage_db;

-- 为 coverage_ranges 表添加 statements 字段
-- statements: 该代码块包含的statement数
ALTER TABLE coverage_ranges 
    ADD COLUMN statements INT NOT NULL DEFAULT 0 COMMENT '该代码块包含的statement数' 
    AFTER end_col;

-- 注意事项：
-- 1. 执行此脚本前请先备份数据库
-- 2. 对于已有数据，statements字段会被设置为默认值0
-- 3. 如果需要重新计算已有数据的statements，需要重新上报覆盖率数据

