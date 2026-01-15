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


def get_git_env():
    """
    获取执行 Git 命令时的环境变量
    配置 SSH 以处理主机密钥验证问题（适用于容器环境）
    
    Returns:
        dict: 包含环境变量的字典
    """
    env = os.environ.copy()
    # 设置 GIT_SSH_COMMAND 以自动接受新的主机密钥（适用于容器环境）
    # 如果 known_hosts 中已有密钥，会正常验证；如果没有，会自动接受
    # 这对于容器环境是安全的，因为容器是临时的
    git_ssh_command = "ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/root/.ssh/known_hosts"
    env['GIT_SSH_COMMAND'] = git_ssh_command
    return env


def get_authenticated_url(repo_url: str) -> str:
    """
    将仓库 URL 转换为带认证信息的 URL（如果配置了 token）
    
    支持的环境变量：
    - GITHUB_TOKEN: GitHub 个人访问令牌
    - GITLAB_TOKEN: GitLab 个人访问令牌
    - BITBUCKET_TOKEN: Bitbucket 应用密码
    - GITEE_TOKEN: Gitee 个人访问令牌
    - GIT_TOKEN: 通用 Git token（用于所有 HTTPS URL）
    
    对于 HTTPS URL，如果有对应的 token，会将其嵌入到 URL 中：
    - https://github.com/owner/repo.git -> https://token@github.com/owner/repo.git
    
    对于 SSH URL，会转换为 HTTPS URL 并使用 token 认证（如果有 token）：
    - git@github.com:owner/repo.git -> https://token@github.com/owner/repo.git
    
    Args:
        repo_url: 原始仓库 URL
    
    Returns:
        str: 带认证信息的 URL（如果有 token），否则返回原 URL 或转换后的 HTTPS URL
    """
    logger.info(f"get_authenticated_url called with: {repo_url}")
    if not repo_url:
        return repo_url
    
    repo_url = repo_url.strip()
    
    # 如果 URL 已经包含认证信息，直接返回
    if '@' in repo_url and (repo_url.startswith('http://') or repo_url.startswith('https://')):
        # 检查是否已经有 token（格式：https://token@host/...）
        if re.match(r'^https?://[^@]+@', repo_url):
            return repo_url
    
    # 处理 SSH URL：git@host:owner/repo.git -> https://host/owner/repo.git
    https_url = None
    if repo_url.startswith('git@'):
        # git@github.com:owner/repo.git -> https://github.com/owner/repo.git
        https_url = repo_url.replace('git@', 'https://', 1).replace(':', '/', 1)
        logger.info(f"Converting SSH URL to HTTPS: {repo_url} -> {https_url}")
    elif repo_url.startswith('http://') or repo_url.startswith('https://'):
        https_url = repo_url
    else:
        # 未知格式，返回原 URL
        logger.warning(f"Unknown URL format: {repo_url}")
        return repo_url
    
    # 提取域名以确定使用哪个 token
    token = None
    if 'github.com' in https_url:
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GIT_TOKEN')
        logger.debug(f"Checking for GitHub token: GITHUB_TOKEN={'***' if os.environ.get('GITHUB_TOKEN') else 'not set'}, GIT_TOKEN={'***' if os.environ.get('GIT_TOKEN') else 'not set'}")
    elif 'gitlab.com' in https_url or 'gitlab' in https_url:
        token = os.environ.get('GITLAB_TOKEN') or os.environ.get('GIT_TOKEN')
    elif 'bitbucket.org' in https_url:
        token = os.environ.get('BITBUCKET_TOKEN') or os.environ.get('GIT_TOKEN')
    elif 'gitee.com' in https_url:
        token = os.environ.get('GITEE_TOKEN') or os.environ.get('GIT_TOKEN')
    else:
        # 对于其他域名，尝试使用通用 token
        token = os.environ.get('GIT_TOKEN')
    
    # 如果有 token，将其嵌入到 URL 中
    if token:
        # 移除可能的用户名部分（如果有）
        # https://user@github.com/owner/repo.git -> https://github.com/owner/repo.git
        url_without_auth = re.sub(r'^https?://[^@]+@', r'https://', https_url)
        # 添加 token
        authenticated_url = url_without_auth.replace('https://', f'https://{token}@', 1)
        logger.info(f"Using token authentication for repository (converted from SSH if applicable)")
        logger.debug(f"Authenticated URL: {authenticated_url[:50]}...")
        return authenticated_url
    
    # 如果没有 token，返回转换后的 HTTPS URL（如果是从 SSH 转换的）
    if https_url != repo_url:
        logger.warning(f"Converted SSH URL to HTTPS but no token available: {repo_url} -> {https_url}")
        logger.warning(f"This may cause authentication issues. Please configure GITHUB_TOKEN or GIT_TOKEN environment variable.")
        return https_url
    
    return repo_url


def ensure_remote_url(repo_url: str) -> bool:
    """
    确保 bare 仓库的 remote URL 使用带认证信息的 URL（如果有 token）
    
    Args:
        repo_url: 原始仓库 URL
    
    Returns:
        bool: 是否成功
    """
    logger.info(f"ensure_remote_url called for: {repo_url}")
    bare_repo_path = get_bare_repo_path(repo_url)
    
    if not os.path.exists(bare_repo_path):
        logger.info(f"Bare repository does not exist yet: {bare_repo_path}")
        return True  # 仓库不存在，会在 clone 时使用正确的 URL
    
    try:
        # 获取带认证信息的 URL
        logger.info(f"Getting authenticated URL for: {repo_url}")
        authenticated_url = get_authenticated_url(repo_url)
        logger.info(f"Authenticated URL result: {authenticated_url[:80]}...")
        
        # 获取当前的 remote URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=bare_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to get current remote URL: {result.stderr}")
            # 如果获取失败，尝试设置 URL
            authenticated_url = get_authenticated_url(repo_url)
            logger.info(f"Setting remote URL to: {authenticated_url[:50]}...")
            result = subprocess.run(
                ['git', 'remote', 'set-url', 'origin', authenticated_url],
                cwd=bare_repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to set remote URL: {result.stderr}")
                return False
            return True
        
        current_url = result.stdout.strip()
        
        # 如果 URL 不同，更新它
        # 注意：即使都是指向同一个仓库，SSH URL 和 HTTPS URL 也是不同的
        if current_url != authenticated_url:
            logger.info(f"Updating remote URL from SSH/old format to HTTPS with token")
            logger.debug(f"Current URL: {current_url}")
            logger.debug(f"New URL: {authenticated_url[:50]}...")
            result = subprocess.run(
                ['git', 'remote', 'set-url', 'origin', authenticated_url],
                cwd=bare_repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to update remote URL: {result.stderr}")
                return False
            logger.info(f"Successfully updated remote URL")
        else:
            logger.debug(f"Remote URL is already up to date")
        
        return True
    except Exception as e:
        logger.error(f"Error ensuring remote URL: {e}")
        return False  # 返回 False，让调用者知道有问题


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
        # 确保 remote URL 使用带认证信息的 URL（如果有 token）
        if not ensure_remote_url(repo_url):
            logger.warning(f"Failed to update remote URL, but continuing with existing repository")
        return True
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(bare_repo_path), exist_ok=True)
        
        # 克隆 bare 仓库
        # 使用带认证信息的 URL（如果有 token）
        authenticated_url = get_authenticated_url(repo_url)
        logger.info(f"Cloning bare repository: {repo_url} to {bare_repo_path}")
        cmd = ['git', 'clone', '--bare', authenticated_url, bare_repo_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            env=get_git_env()
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
        # 确保 remote URL 使用带认证信息的 URL
        if not ensure_remote_url(repo_url):
            logger.error(f"Failed to ensure remote URL is using authenticated format")
            return False
        
        # 验证 remote URL 确实已更新（用于调试）
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=bare_repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            current_remote_url = result.stdout.strip()
            logger.debug(f"Current remote URL: {current_remote_url[:50]}...")
            # 如果仍然是 SSH URL，说明更新失败
            if current_remote_url.startswith('git@'):
                logger.error(f"Remote URL is still using SSH format: {current_remote_url}")
                logger.error(f"This indicates the URL update failed. Please check token configuration.")
                return False
        
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
            timeout=300,  # 5分钟超时
            env=get_git_env()
        )
        
        if result.returncode != 0:
            # 如果直接 fetch commit 失败，尝试 fetch 所有分支
            logger.warning(f"Failed to fetch commit {commit} directly, trying to fetch all branches")
            result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=bare_repo_path,
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                env=get_git_env()
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
