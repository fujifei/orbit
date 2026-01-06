#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库模型层
提供所有数据库模型和数据库连接管理
"""

import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, BigInteger, Index, text, func
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# 数据库配置
DATABASE_DSN = "mysql+pymysql://agile:agile@127.0.0.1:6666/coverage_db?charset=utf8mb4"

# 创建数据库引擎
engine = create_engine(
    DATABASE_DSN,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=90,
    pool_pre_ping=True,
    echo=False
)

# 创建会话工厂
SessionLocal = scoped_session(sessionmaker(bind=engine))

# 创建基础模型类
Base = declarative_base()


# CoverageReport 覆盖率报告模型
class CoverageReport(Base):
    __tablename__ = 'coverage_reports'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(String(64), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, default='', index=True)  # 仓库名称，保留用于快速搜索
    branch = Column(String(255), nullable=False, index=True)
    base_branch = Column(String(255), default='master')  # 基准分支
    commit = Column(String(100), nullable=False, index=True)
    base_commit = Column(String(100), default='')  # 基准 commit
    ci_provider = Column(String(50))
    ci_pipeline_id = Column(String(255))
    ci_job_id = Column(String(255))
    coverage_format = Column(String(50), nullable=False, default='goc')
    coverage_raw = Column(Text)  # API不需要，consumer需要
    status = Column(String(50), nullable=False, default='pending', index=True)
    error_message = Column(Text)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    
    def to_dict(self, config=None):
        """
        转换为字典，用于API响应
        
        参数:
            config: CoverageConfig 对象（可选），用于填充 repo_url
        """
        result = {
            'id': self.id,
            'repo_id': self.repo_id,
            'repo_name': self.repo_name,
            'branch': self.branch,
            'base_branch': self.base_branch,
            'commit': self.commit,
            'base_commit': self.base_commit,
            'ci_provider': self.ci_provider,
            'ci_pipeline_id': self.ci_pipeline_id,
            'ci_job_id': self.ci_job_id,
            'coverage_format': self.coverage_format,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # 如果提供了config，添加 repo_url
        if config:
            result['repo_url'] = config.repo_url
        
        # 如果存在error_message，也包含进去
        if hasattr(self, 'error_message') and self.error_message:
            result['error_message'] = self.error_message
        return result


# CoverageFile 覆盖率文件模型
class CoverageFile(Base):
    __tablename__ = 'coverage_files'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(String(64), nullable=False, index=True)
    branch = Column(String(255), nullable=False, index=True)
    file_path = Column(String(500), nullable=False, index=True)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            'id': self.id,
            'repo_id': self.repo_id,
            'branch': self.branch,
            'file': self.file_path,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


# CoverageRange 覆盖率范围模型
class CoverageRange(Base):
    __tablename__ = 'coverage_ranges'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, nullable=False, index=True)
    start_line = Column(Integer, nullable=False)
    start_col = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    end_col = Column(Integer, nullable=False)
    statements = Column(Integer, nullable=False, default=0)  # 该代码块包含的statement数
    hit = Column(Integer, nullable=False, default=0, index=True)  # 执行次数(count)
    created_at = Column(BigInteger, nullable=False)
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            'id': self.id,
            'startLine': self.start_line,
            'startCol': self.start_col,
            'endLine': self.end_line,
            'endCol': self.end_col,
            'statements': self.statements,
            'hit': self.hit,
            'created_at': self.created_at
        }


# CoverageConfig 配置模型
class CoverageConfig(Base):
    __tablename__ = 'coverage_config'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(String(64), nullable=False, unique=True, index=True)
    repo_name = Column(String(255), nullable=False, default='', index=True)  # 仓库名称
    repo_url = Column(String(500), nullable=False, default='')  # 仓库链接
    repo_type = Column(Integer, nullable=False, default=1, index=True)  # 仓库类型：1=go, 2=python, 3=java
    base_branch = Column(String(255), nullable=False, default='master')
    exclude_dirs = Column(Text)  # 排除目录，分号分隔
    exclude_files = Column(Text)  # 排除文件后缀，分号分隔
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)
    
    def to_dict(self):
        """转换为字典，用于API响应"""
        return {
            'id': self.id,
            'repo_id': self.repo_id,
            'repo_name': self.repo_name,
            'repo_url': self.repo_url,
            'repo_type': self.repo_type,
            'base_branch': self.base_branch,
            'exclude_dirs': self.exclude_dirs or '',
            'exclude_files': self.exclude_files or '',
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


def get_db_session():
    """获取数据库会话"""
    return SessionLocal()


def close_db_session():
    """关闭数据库会话（用于Flask teardown）"""
    SessionLocal.remove()


def init_db():
    """初始化数据库连接并测试"""
    try:
        db = SessionLocal()
        db.execute(text('SELECT 1'))
        logger.info("Database connection established")
        
        # 测试查询表是否存在
        try:
            count = db.query(func.count(CoverageReport.id)).scalar()
            logger.info(f"Database table 'coverage_reports' exists, current record count: {count}")
        except Exception as e:
            logger.warning(f"Failed to query coverage_reports table: {e}")
            logger.warning("This might indicate the table doesn't exist or there's a connection issue")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

