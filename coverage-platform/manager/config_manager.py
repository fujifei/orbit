#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
处理仓库配置的增删改查等业务逻辑
"""

import logging
import time
from typing import Optional, Dict, List, Any

from models import CoverageConfig, get_db_session
from manager.diff_manager import set_base_branch_for_repo

logger = logging.getLogger(__name__)


def extract_repo_name(repo_url: str) -> str:
    """
    从仓库URL中提取仓库名称
    例如: https://github.com/fujifei/tuna.git -> tuna
    """
    if not repo_url:
        return ''
    
    # 移除 .git 后缀
    url = repo_url.rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
    
    # 提取最后一个路径部分
    parts = url.split('/')
    if parts:
        return parts[-1]
    
    return ''


def get_all_configs(repo_name: Optional[str] = None) -> Dict[str, Any]:
    """
    获取所有仓库配置列表
    
    参数:
        repo_name: 仓库名称（可选，模糊搜索）
    
    返回:
        {
            'data': [配置列表],
            'total': 总数
        }
    """
    try:
        db = get_db_session()
        
        # 构建查询
        query = db.query(CoverageConfig)
        
        # 支持按仓库名称模糊搜索
        if repo_name:
            query = query.filter(CoverageConfig.repo_name.like(f'%{repo_name}%'))
        
        # 按创建时间倒序排列
        configs = query.order_by(CoverageConfig.created_at.desc()).all()
        
        return {
            'data': [config.to_dict() for config in configs],
            'total': len(configs)
        }
    except Exception as e:
        logger.error(f"Error getting configs: {e}")
        raise


def get_config_by_repo_id(repo_id: str) -> Optional[Dict[str, Any]]:
    """
    获取单个仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    
    返回:
        配置字典，如果不存在返回 None
    """
    try:
        db = get_db_session()
        
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if not config:
            return None
        
        return config.to_dict()
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise


def get_repo_config_with_default(repo_id: str) -> Dict[str, Any]:
    """
    获取仓库配置，如果不存在返回默认配置
    
    参数:
        repo_id: 仓库唯一标识
    
    返回:
        配置字典（如果不存在返回默认值）
    """
    try:
        db = get_db_session()
        
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if not config:
            # 返回默认配置
            return {
                'repo_id': repo_id,
                'base_branch': 'master'
            }
        
        return config.to_dict()
    except Exception as e:
        logger.error(f"Error getting repo config: {e}")
        raise


def create_config(
    repo_url: str,
    repo_id: str,
    base_branch: str = 'master',
    exclude_dirs: str = '',
    exclude_files: str = ''
) -> Dict[str, Any]:
    """
    创建仓库配置
    
    参数:
        repo_url: 仓库 URL
        repo_id: 仓库唯一标识
        base_branch: 基准分支（默认 master）
        exclude_dirs: 排除的目录（分号分隔）
        exclude_files: 排除的文件（分号分隔）
    
    返回:
        创建的配置字典
    
    异常:
        ValueError: 参数校验失败
        RuntimeError: 配置已存在或创建失败
    """
    try:
        repo_url = repo_url.strip()
        repo_id = repo_id.strip()
        base_branch = base_branch.strip()
        exclude_dirs = exclude_dirs.strip()
        exclude_files = exclude_files.strip()
        
        if not repo_url or not repo_id:
            raise ValueError('Missing repo_url or repo_id')
        
        # 从 repo_url 提取 repo_name
        repo_name = extract_repo_name(repo_url)
        if not repo_name:
            raise ValueError('Failed to extract repo_name from repo_url')
        
        db = get_db_session()
        
        # 检查是否已存在
        existing = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if existing:
            raise RuntimeError('Config already exists for this repo_id')
        
        # 创建配置
        now = int(time.time() * 1000)
        config = CoverageConfig(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=repo_url,
            base_branch=base_branch,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
            created_at=now,
            updated_at=now
        )
        
        db.add(config)
        db.commit()
        
        logger.info(f"Created config for repo_id={repo_id}, repo_name={repo_name}")
        
        return config.to_dict()
    except Exception as e:
        logger.error(f"Error creating config: {e}")
        db.rollback()
        raise


def update_config(
    repo_id: str,
    base_branch: Optional[str] = None,
    exclude_dirs: Optional[str] = None,
    exclude_files: Optional[str] = None
) -> Dict[str, Any]:
    """
    更新仓库配置
    
    参数:
        repo_id: 仓库唯一标识
        base_branch: 基准分支（可选）
        exclude_dirs: 排除的目录（可选）
        exclude_files: 排除的文件（可选）
    
    返回:
        更新后的配置字典
    
    异常:
        RuntimeError: 配置不存在
    """
    try:
        db = get_db_session()
        
        # 查找配置
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if not config:
            raise RuntimeError('Config not found')
        
        # 更新字段
        if base_branch is not None:
            config.base_branch = base_branch.strip()
        if exclude_dirs is not None:
            config.exclude_dirs = exclude_dirs.strip()
        if exclude_files is not None:
            config.exclude_files = exclude_files.strip()
        
        config.updated_at = int(time.time() * 1000)
        
        db.commit()
        
        logger.info(f"Updated config for repo_id={repo_id}")
        
        return config.to_dict()
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        db.rollback()
        raise


def delete_config(repo_id: str) -> bool:
    """
    删除仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    
    返回:
        是否删除成功
    
    异常:
        RuntimeError: 配置不存在
    """
    try:
        db = get_db_session()
        
        # 查找配置
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if not config:
            raise RuntimeError('Config not found')
        
        db.delete(config)
        db.commit()
        
        logger.info(f"Deleted config for repo_id={repo_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        db.rollback()
        raise


def set_repo_config(repo_id: str, base_branch: str) -> bool:
    """
    设置仓库配置（仅设置 base_branch）
    
    参数:
        repo_id: 仓库唯一标识
        base_branch: 基准分支
    
    返回:
        是否设置成功
    """
    try:
        if not base_branch:
            raise ValueError('Missing base_branch')
        
        # 调用 diff_manager 中的方法设置基准分支
        success = set_base_branch_for_repo(repo_id, base_branch)
        if not success:
            raise RuntimeError('Failed to set config')
        
        return True
    except Exception as e:
        logger.error(f"Error setting repo config: {e}")
        raise

