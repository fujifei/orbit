-- 创建数据库
CREATE DATABASE IF NOT EXISTS coverage_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE coverage_db;

-- 创建覆盖率文件表
CREATE TABLE IF NOT EXISTS coverage_files (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_file_path (file_path(255)),
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
    hit INT NOT NULL DEFAULT 0 COMMENT '命中次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (file_id) REFERENCES coverage_files(id) ON DELETE CASCADE,
    INDEX idx_file_id (file_id),
    INDEX idx_hit (hit)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='覆盖率范围表';

