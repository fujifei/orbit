#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
处理仓库配置的增删改查等业务逻辑
"""

import logging
import time
import re
import requests
from typing import Optional, Dict, List, Any, Union

from models import CoverageConfig, get_db_session
from manager.diff_manager import set_base_branch_for_repo
from manager.repo_manager import extract_project_name

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


def get_all_configs(repo_name: Optional[str] = None, repo_type: Optional[int] = None) -> Dict[str, Any]:
    """
    获取所有仓库配置列表
    
    参数:
        repo_name: 仓库名称（可选，模糊搜索）
        repo_type: 仓库类型（可选，1=go, 2=python, 3=java）
    
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
        
        # 支持按仓库类型过滤
        if repo_type is not None:
            query = query.filter(CoverageConfig.repo_type == repo_type)
        
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
    repo_id: Union[str, int],
    base_branch: str = 'master',
    exclude_dirs: str = '',
    exclude_files: str = '',
    repo_type: int = 1
) -> Dict[str, Any]:
    """
    创建仓库配置
    
    参数:
        repo_url: 仓库 URL
        repo_id: 仓库唯一标识（整数或字符串，GitHub仓库ID）
        base_branch: 基准分支（默认 master）
        exclude_dirs: 排除的目录（分号分隔）
        exclude_files: 排除的文件（分号分隔）
        repo_type: 仓库类型（默认 1，1=go, 2=python, 3=java）
    
    返回:
        创建的配置字典
    
    异常:
        ValueError: 参数校验失败
        RuntimeError: 配置已存在或创建失败
    """
    try:
        repo_url = repo_url.strip()
        # repo_id 可能是整数或字符串，统一转换为字符串存储
        repo_id_str = str(repo_id).strip() if repo_id is not None else ''
        base_branch = base_branch.strip()
        exclude_dirs = exclude_dirs.strip()
        exclude_files = exclude_files.strip()
        
        if not repo_url or not repo_id_str:
            raise ValueError('Missing repo_url or repo_id')
        
        # 验证 repo_type 值
        if repo_type not in [1, 2, 3]:
            raise ValueError('Invalid repo_type, must be 1 (go), 2 (python), or 3 (java)')
        
        # 从 repo_url 提取 repo_name
        repo_name = extract_repo_name(repo_url)
        if not repo_name:
            raise ValueError('Failed to extract repo_name from repo_url')
        
        db = get_db_session()
        
        # 检查是否已存在
        existing = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id_str
        ).first()
        
        if existing:
            raise RuntimeError('Config already exists for this repo_id')
        
        # 创建配置
        now = int(time.time() * 1000)
        config = CoverageConfig(
            repo_id=repo_id_str,
            repo_name=repo_name,
            repo_url=repo_url,
            repo_type=repo_type,
            base_branch=base_branch,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
            created_at=now,
            updated_at=now
        )
        
        db.add(config)
        db.commit()
        
        logger.info(f"Created config for repo_id={repo_id_str}, repo_name={repo_name}, repo_type={repo_type}")
        
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


def extract_github_owner_repo(repo_url: str) -> tuple:
    """
    从仓库URL中提取GitHub的owner和repo名称
    
    参数:
        repo_url: 仓库URL（支持 git@ 和 https:// 格式）
    
    返回:
        tuple: (owner, repo) 例如: ('fujifei', 'tuna-java')
    
    异常:
        ValueError: 仓库URL格式不正确或不是GitHub仓库
    """
    if not repo_url:
        raise ValueError('Missing repo_url')
    
    repo_url = repo_url.strip()
    
    # 移除 .git 后缀
    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    
    # 处理 git@host:owner/repo 格式
    if repo_url.startswith('git@'):
        # git@github.com:fujifei/tuna-java -> github.com/fujifei/tuna-java
        repo_url = repo_url.replace('git@', '', 1).replace(':', '/', 1)
    
    # 处理 https:// 或 http:// 格式
    if repo_url.startswith('http://') or repo_url.startswith('https://'):
        # https://github.com/fujifei/tuna-java -> github.com/fujifei/tuna-java
        repo_url = re.sub(r'^https?://', '', repo_url)
    
    # 移除末尾的斜杠
    repo_url = repo_url.rstrip('/')
    
    # 检查是否是GitHub仓库
    if not repo_url.startswith('github.com/'):
        raise ValueError('Only GitHub repositories are supported')
    
    # 提取 owner 和 repo
    # github.com/fujifei/tuna-java -> ('fujifei', 'tuna-java')
    parts = repo_url.replace('github.com/', '').split('/')
    if len(parts) < 2:
        raise ValueError('Invalid GitHub repository URL format')
    
    owner = parts[0]
    repo = parts[1]
    
    return (owner, repo)


def get_repo_id_from_url(repo_url: str) -> int:
    """
    根据仓库URL从GitHub API获取RepoID（整数）
    
    参数:
        repo_url: 仓库URL（支持 git@ 和 https:// 格式，仅支持GitHub）
    
    返回:
        int: RepoID（GitHub仓库的唯一整数标识）
    
    异常:
        ValueError: 仓库URL格式不正确或不是GitHub仓库
        RuntimeError: 无法从GitHub API获取仓库信息
    """
    if not repo_url:
        raise ValueError('Missing repo_url')
    
    try:
        # 提取 owner 和 repo
        owner, repo = extract_github_owner_repo(repo_url)
        
        # 调用 GitHub API 获取仓库信息
        api_url = f'https://api.github.com/repos/{owner}/{repo}'
        logger.info(f"Fetching repository ID from GitHub API: {api_url}")
        
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 404:
            raise RuntimeError(f'Repository not found: {owner}/{repo}')
        elif response.status_code == 403:
            # 可能是速率限制
            raise RuntimeError('GitHub API rate limit exceeded. Please try again later.')
        elif response.status_code != 200:
            raise RuntimeError(f'Failed to fetch repository info from GitHub API: HTTP {response.status_code}')
        
        data = response.json()
        repo_id = data.get('id')
        
        if not repo_id or not isinstance(repo_id, int):
            raise RuntimeError('Invalid repository ID from GitHub API')
        
        logger.info(f"Successfully fetched repository ID: {repo_id} for {owner}/{repo}")
        return repo_id
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching repository ID: {e}")
        raise RuntimeError(f'Network error: {str(e)}')
    except ValueError as e:
        # 重新抛出 ValueError
        raise
    except Exception as e:
        logger.error(f"Error getting repo_id from GitHub API: {e}")
        raise RuntimeError(f'Failed to get repository ID: {str(e)}')

