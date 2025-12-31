#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
代码仓库管理模块
负责拉取和管理远程代码仓库
使用 bare clone + worktree 方式管理多个 commit
"""

import os
import subprocess
import logging
import re
import fcntl
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# repos目录路径（在coverage-platform目录下）
# 获取 manager 目录的父目录（即 coverage-platform 目录）
REPOS_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'repos')


def extract_project_name(repo_url: str) -> str:
    """
    从git仓库URL中提取项目名称
    例如：
    - git@github.com:fujifei/tuna.git -> github.com/fujifei/tuna
    - https://github.com/fujifei/tuna.git -> github.com/fujifei/tuna
    - git@gitlab.com:group/project.git -> gitlab.com/group/project
    
    Args:
        repo_url: git仓库URL
    
    Returns:
        str: 项目名称路径，如 github.com/fujifei/tuna
    """
    # 移除末尾的斜杠
    repo_url = repo_url.rstrip('/')
    
    # 移除 .git 后缀（精确匹配）
    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    
    # 处理 git@host:path 格式
    if repo_url.startswith('git@'):
        # git@github.com:fujifei/tuna -> github.com/fujifei/tuna
        repo_url = repo_url.replace('git@', '', 1).replace(':', '/', 1)
    # 处理 https:// 或 http:// 格式
    elif repo_url.startswith('http://') or repo_url.startswith('https://'):
        # https://github.com/fujifei/tuna -> github.com/fujifei/tuna
        repo_url = re.sub(r'^https?://', '', repo_url)
    # 处理 git:// 格式
    elif repo_url.startswith('git://'):
        # git://github.com/fujifei/tuna -> github.com/fujifei/tuna
        repo_url = repo_url.replace('git://', '', 1)
    
    # 移除末尾的斜杠
    repo_url = repo_url.rstrip('/')
    
    return repo_url


def get_repo_dir(repo_url: str) -> str:
    """
    根据仓库URL获取本地仓库目录路径
    使用项目名称作为目录名，例如：github.com/fujifei/tuna
    
    Args:
        repo_url: git仓库URL
    
    Returns:
        str: 本地仓库目录路径
    """
    project_name = extract_project_name(repo_url)
    return os.path.join(REPOS_BASE_DIR, project_name)


def get_bare_repo_path(repo_url: str) -> str:
    """
    获取 bare 仓库路径
    例如：repos/github.com/fujifei/tuna/repo.git
    
    Args:
        repo_url: git仓库URL
    
    Returns:
        str: bare 仓库路径
    """
    repo_dir = get_repo_dir(repo_url)
    return os.path.join(repo_dir, 'repo.git')


def get_worktree_dir(repo_url: str, commit: str) -> str:
    """
    获取指定 commit 的 worktree 目录路径
    例如：repos/github.com/fujifei/tuna/worktrees/commitidxxx
    
    Args:
        repo_url: git仓库URL
        commit: commit hash
    
    Returns:
        str: worktree 目录路径
    """
    repo_dir = get_repo_dir(repo_url)
    return os.path.join(repo_dir, 'worktrees', commit)


def get_commit_lock_path(repo_url: str, commit: str) -> str:
    """
    获取 commit 级别的锁文件路径
    例如：repos/github.com/fujifei/tuna/worktrees/.lock_commitidxxx
    
    Args:
        repo_url: git仓库URL
        commit: commit hash
    
    Returns:
        str: 锁文件路径
    """
    repo_dir = get_repo_dir(repo_url)
    worktrees_dir = os.path.join(repo_dir, 'worktrees')
    return os.path.join(worktrees_dir, f'.lock_{commit}')


def ensure_repos_dir():
    """
    确保repos目录存在
    """
    os.makedirs(REPOS_BASE_DIR, exist_ok=True)


class CommitLock:
    """
    Commit 级别的文件锁，用于防止并发创建同一个 commit 的 worktree
    """
    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self.lock_file = None
    
    def __enter__(self):
        # 确保锁文件目录存在
        os.makedirs(os.path.dirname(self.lock_path), exist_ok=True)
        
        # 打开锁文件（如果不存在则创建）
        self.lock_file = open(self.lock_path, 'w')
        
        # 尝试获取排他锁（非阻塞）
        max_retries = 30  # 最多等待30秒
        retry_count = 0
        while retry_count < max_retries:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"Acquired lock for {self.lock_path}")
                return self
            except IOError:
                # 锁被占用，等待后重试
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(1)
                    logger.debug(f"Waiting for lock {self.lock_path}, retry {retry_count}/{max_retries}")
                else:
                    raise Exception(f"Failed to acquire lock after {max_retries} retries: {self.lock_path}")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                logger.debug(f"Released lock for {self.lock_path}")
            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")


def ensure_bare_repo(repo_url: str) -> bool:
    """
    确保 bare 仓库存在，如果不存在则克隆
    
    Args:
        repo_url: 仓库URL
    
    Returns:
        bool: 是否成功
    """
    bare_repo_path = get_bare_repo_path(repo_url)
    project_name = extract_project_name(repo_url)
    
    # 检查 bare 仓库是否已存在
    if os.path.exists(bare_repo_path) and os.path.exists(os.path.join(bare_repo_path, 'HEAD')):
        logger.info(f"Bare repository already exists: {bare_repo_path}")
        return True
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(bare_repo_path), exist_ok=True)
        
        # 克隆 bare 仓库
        logger.info(f"Cloning bare repository: {repo_url} to {bare_repo_path}")
        cmd = ['git', 'clone', '--bare', repo_url, bare_repo_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to clone bare repository: {result.stderr}")
            return False
        
        logger.info(f"Successfully cloned bare repository: {project_name}")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while cloning bare repository: {repo_url}")
        return False
    except Exception as e:
        logger.error(f"Error cloning bare repository: {e}")
        return False


def fetch_commit(repo_url: str, commit: str) -> bool:
    """
    从远程获取指定的 commit（如果本地不存在）
    
    Args:
        repo_url: 仓库URL
        commit: commit hash
    
    Returns:
        bool: 是否成功
    """
    bare_repo_path = get_bare_repo_path(repo_url)
    
    try:
        # 检查 commit 是否已存在
        result = subprocess.run(
            ['git', 'cat-file', '-e', commit],
            cwd=bare_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # commit 已存在
            return True
        
        # commit 不存在，需要 fetch
        logger.info(f"Fetching commit {commit} from remote")
        result = subprocess.run(
            ['git', 'fetch', 'origin', commit],
            cwd=bare_repo_path,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        if result.returncode != 0:
            # 如果直接 fetch commit 失败，尝试 fetch 所有分支
            logger.warning(f"Failed to fetch commit {commit} directly, trying to fetch all branches")
            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=bare_repo_path,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to fetch from remote: {result.stderr}")
                return False
        
        # 再次检查 commit 是否存在
        result = subprocess.run(
            ['git', 'cat-file', '-e', commit],
            cwd=bare_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully fetched commit {commit}")
            return True
        else:
            logger.error(f"Commit {commit} still not found after fetch")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while fetching commit {commit}")
        return False
    except Exception as e:
        logger.error(f"Error fetching commit {commit}: {e}")
        return False


def ensure_worktree(repo_url: str, commit: str) -> bool:
    """
    确保指定 commit 的 worktree 存在，如果不存在则创建
    
    Args:
        repo_url: 仓库URL
        commit: commit hash
    
    Returns:
        bool: 是否成功
    """
    worktree_dir = get_worktree_dir(repo_url, commit)
    bare_repo_path = get_bare_repo_path(repo_url)
    
    # 检查 worktree 是否已存在
    if os.path.exists(worktree_dir) and os.path.exists(os.path.join(worktree_dir, '.git')):
        # 验证 worktree 是否指向正确的 commit
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=worktree_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip() == commit:
                logger.info(f"Worktree already exists and points to correct commit: {commit}")
                return True
            else:
                logger.warning(f"Worktree exists but points to different commit, removing it")
                import shutil
                shutil.rmtree(worktree_dir)
        except Exception as e:
            logger.warning(f"Error checking worktree commit, removing it: {e}")
            import shutil
            shutil.rmtree(worktree_dir)
    
    # 使用锁防止并发创建
    lock_path = get_commit_lock_path(repo_url, commit)
    with CommitLock(lock_path):
        # 再次检查（可能在等待锁的过程中，其他进程已经创建了）
        if os.path.exists(worktree_dir) and os.path.exists(os.path.join(worktree_dir, '.git')):
            logger.info(f"Worktree was created by another process: {commit}")
            return True
        
        try:
            # 确保 worktrees 目录存在
            os.makedirs(os.path.dirname(worktree_dir), exist_ok=True)
            
            # 创建 worktree
            logger.info(f"Creating worktree for commit {commit} at {worktree_dir}")
            cmd = ['git', '--git-dir', bare_repo_path, 'worktree', 'add', worktree_dir, commit]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to create worktree: {result.stderr}")
                return False
            
            logger.info(f"Successfully created worktree for commit {commit}")
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while creating worktree for commit {commit}")
            return False
        except Exception as e:
            logger.error(f"Error creating worktree for commit {commit}: {e}")
            return False


def clone_or_update_repo(repo_url: str, repo_id: str, branch: str, commit: str) -> bool:
    """
    克隆或更新代码仓库（使用 bare + worktree 方式）
    
    Args:
        repo_url: 仓库URL
        repo_id: 仓库唯一标识（保留用于日志，实际使用repo_url）
        branch: 分支名（用于 fetch，实际使用 commit）
        commit: commit hash
    
    Returns:
        bool: 是否成功
    """
    try:
        ensure_repos_dir()
        project_name = extract_project_name(repo_url)
        
        # 1. 确保 bare 仓库存在
        if not ensure_bare_repo(repo_url):
            logger.error(f"Failed to ensure bare repository: {project_name}")
            return False
        
        # 2. 确保 commit 存在（如果不存在则 fetch）
        if not fetch_commit(repo_url, commit):
            logger.error(f"Failed to fetch commit {commit} for repository: {project_name}")
            return False
        
        # 3. 确保 worktree 存在（如果不存在则创建）
        if not ensure_worktree(repo_url, commit):
            logger.error(f"Failed to ensure worktree for commit {commit} in repository: {project_name}")
            return False
        
        logger.info(f"Successfully ensured repository state: {project_name}, commit {commit}")
        return True
    except Exception as e:
        logger.error(f"Failed to clone/update repo {repo_url}: {e}")
        return False


def get_file_content(repo_url: str, commit: str, file_path: str) -> Optional[str]:
    """
    获取指定仓库、commit和文件路径的文件内容
    从 worktree 目录读取文件
    
    Args:
        repo_url: 仓库URL（用于确定项目目录）
        commit: commit hash
        file_path: 文件路径（相对于仓库根目录，可能包含模块前缀如tuna/models/xxx.go）
    
    Returns:
        str: 文件内容，如果文件不存在返回None
    """
    try:
        worktree_dir = get_worktree_dir(repo_url, commit)
        
        if not os.path.exists(worktree_dir):
            logger.warning(f"Worktree directory not found: {worktree_dir} for commit {commit}")
            return None
        
        # 构建完整文件路径
        full_path = os.path.join(worktree_dir, file_path)
        
        # 检查文件是否存在
        if os.path.exists(full_path) and os.path.isfile(full_path):
            # 读取文件内容
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return content
        
        # 如果文件不存在，尝试去掉第一个路径段（通常是模块名，如tuna/）
        # 例如：tuna/models/user_repository.go -> models/user_repository.go
        path_parts = file_path.split('/')
        adjusted_full_path = None
        if len(path_parts) > 1:
            # 去掉第一个路径段
            adjusted_path = '/'.join(path_parts[1:])
            adjusted_full_path = os.path.join(worktree_dir, adjusted_path)
            
            if os.path.exists(adjusted_full_path) and os.path.isfile(adjusted_full_path):
                logger.info(f"File found after removing prefix: {adjusted_path} (original: {file_path})")
                with open(adjusted_full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                return content
        
        # 如果还是找不到，尝试在仓库根目录直接查找文件名
        filename = os.path.basename(file_path)
        if filename:
            # 递归查找文件
            for root, dirs, files in os.walk(worktree_dir):
                if filename in files:
                    found_path = os.path.join(root, filename)
                    logger.info(f"File found by name: {found_path} (original: {file_path})")
                    with open(found_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    return content
        
        # 记录所有尝试过的路径
        tried_paths = [full_path]
        if adjusted_full_path:
            tried_paths.append(adjusted_full_path)
        logger.warning(f"File not found after trying: {', '.join(tried_paths)}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {file_path} from repo {repo_url} at commit {commit}: {e}")
        return None
