#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增量覆盖率业务逻辑管理层
提供增量覆盖率计算、基准 commit 获取等业务逻辑
"""

import logging
import time
import subprocess
import os
import re
from typing import Dict, List, Optional, Tuple

from models import (
    CoverageReport, CoverageFile, CoverageRange, CoverageConfig,
    get_db_session
)
from manager.repo_manager import get_worktree_dir, get_bare_repo_path
from diff_coverage import (
    CoverageBlock, CoverageIndex, DiffCoverageFile, DiffCoverageSummary,
    parse_git_diff, build_coverage_index, merge_diff_and_coverage,
    generate_diff_coverage_summary, generate_monaco_dataset
)

logger = logging.getLogger(__name__)


def find_go_module_mapping(worktree_dir: str) -> Dict[str, str]:
    """
    在worktree目录中查找所有go.mod文件，构建module名称到文件系统路径的映射
    
    Args:
        worktree_dir: worktree目录路径
    
    Returns:
        Dict[str, str]: module名称 -> 相对路径的映射
        例如: {"tuna": "backend/", "tuna/utils": "backend/utils/"}
    """
    module_mapping = {}
    
    try:
        # 遍历worktree目录，查找所有go.mod文件
        for root, dirs, files in os.walk(worktree_dir):
            if 'go.mod' in files:
                go_mod_path = os.path.join(root, 'go.mod')
                rel_dir = os.path.relpath(root, worktree_dir)
                
                # 读取go.mod文件，提取module名称
                try:
                    with open(go_mod_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 查找module声明：module xxx
                        match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
                        if match:
                            module_name = match.group(1)
                            
                            # 如果目录是当前目录（.），则路径为空
                            if rel_dir == '.':
                                module_mapping[module_name] = ''
                            else:
                                # 确保目录路径以/结尾
                                module_mapping[module_name] = rel_dir + '/'
                            
                            logger.debug(f"Found Go module: {module_name} -> {rel_dir}")
                except Exception as e:
                    logger.warning(f"Failed to parse go.mod at {go_mod_path}: {e}")
    except Exception as e:
        logger.error(f"Failed to scan worktree for go.mod files: {e}")
    
    return module_mapping


def convert_module_path_to_fs_path(module_path: str, module_mapping: Dict[str, str]) -> List[str]:
    """
    将Go module路径转换为文件系统路径
    
    Args:
        module_path: Go module路径，例如 "tuna/api/api.go"
        module_mapping: module名称到文件系统路径的映射
    
    Returns:
        List[str]: 可能的文件系统路径列表，例如 ["backend/api/api.go", "api/api.go"]
    """
    possible_paths = []
    
    # 尝试每个module映射
    for module_name, fs_prefix in module_mapping.items():
        if module_path.startswith(module_name + '/') or module_path == module_name:
            # 移除module前缀
            if module_path == module_name:
                relative_path = ''
            else:
                relative_path = module_path[len(module_name) + 1:]  # +1 for the '/'
            
            # 组合文件系统路径
            if fs_prefix:
                fs_path = fs_prefix + relative_path
            else:
                fs_path = relative_path
            
            possible_paths.append(fs_path)
    
    # 如果没有找到匹配的module，也尝试原始路径
    if not possible_paths:
        possible_paths.append(module_path)
    
    return possible_paths


def get_base_branch_for_repo(repo_id: str) -> str:
    """
    获取指定仓库的基准分支
    
    Args:
        repo_id: 仓库唯一标识
    
    Returns:
        str: 基准分支名，默认为 'master'
    """
    db = get_db_session()
    try:
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if config:
            return config.base_branch
        
        # 如果没有配置，返回默认值
        return 'master'
    finally:
        db.close()


def set_base_branch_for_repo(repo_id: str, base_branch: str) -> bool:
    """
    设置指定仓库的基准分支
    
    Args:
        repo_id: 仓库唯一标识
        base_branch: 基准分支名
    
    Returns:
        bool: 是否成功
    """
    db = get_db_session()
    try:
        now = int(time.time() * 1000)
        
        # 查找是否已存在配置
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == repo_id
        ).first()
        
        if config:
            # 更新
            config.base_branch = base_branch
            config.updated_at = now
        else:
            # 创建
            config = CoverageConfig(
                repo_id=repo_id,
                base_branch=base_branch,
                created_at=now,
                updated_at=now
            )
            db.add(config)
        
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to set base branch: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_base_commit_from_git(repo_path: str, base_branch: str, target_commit: str) -> Optional[str]:
    """
    从 Git 仓库获取基准 commit
    使用 merge-base 找到最近的公共祖先
    
    Args:
        repo_path: 仓库本地路径
        base_branch: 基准分支
        target_commit: 目标 commit
    
    Returns:
        Optional[str]: 基准 commit hash，失败返回 None
    """
    try:
        # 使用 git merge-base 找到公共祖先
        cmd = ['git', 'merge-base', base_branch, target_commit]
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to get merge-base: {result.stderr}")
            
            # 如果 merge-base 失败，尝试直接获取基准分支的 HEAD
            cmd = ['git', 'rev-parse', base_branch]
            result = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to get base branch HEAD: {result.stderr}")
                return None
        
        base_commit = result.stdout.strip()
        return base_commit
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout getting base commit")
        return None
    except Exception as e:
        logger.error(f"Error getting base commit: {e}")
        return None


def get_coverage_blocks_for_file(
    repo_id: str, 
    branch: str, 
    file_path: str,
    repo_url: Optional[str] = None,
    commit: Optional[str] = None
) -> List[CoverageBlock]:
    """
    获取指定文件的覆盖率 blocks
    
    Args:
        repo_id: 仓库唯一标识
        branch: 分支名
        file_path: 文件路径（文件系统路径，如 backend/api/api.go）
        repo_url: 仓库URL（可选，用于路径转换）
        commit: commit hash（可选，用于路径转换）
    
    Returns:
        List[CoverageBlock]: 覆盖率 block 列表
    """
    db = get_db_session()
    try:
        # 首先尝试直接查找文件
        file = db.query(CoverageFile).filter(
            CoverageFile.repo_id == repo_id,
            CoverageFile.branch == branch,
            CoverageFile.file_path == file_path
        ).first()
        
        # 如果找不到文件，尝试进行路径转换
        if not file and repo_url and commit:
            # 获取worktree目录
            worktree_dir = get_worktree_dir(repo_url, commit)
            
            if worktree_dir and os.path.exists(worktree_dir):
                # 构建module映射
                module_mapping = find_go_module_mapping(worktree_dir)
                logger.debug(f"Module mapping for {repo_url}@{commit}: {module_mapping}")
                
                # 查询该repo_id+branch下的所有文件路径
                all_files = db.query(CoverageFile).filter(
                    CoverageFile.repo_id == repo_id,
                    CoverageFile.branch == branch
                ).all()
                
                # 对每个数据库中的文件路径，尝试转换为文件系统路径
                for db_file in all_files:
                    possible_paths = convert_module_path_to_fs_path(db_file.file_path, module_mapping)
                    
                    # 如果转换后的路径匹配目标file_path，则使用该文件
                    if file_path in possible_paths:
                        logger.info(f"Path mapping found: {file_path} -> {db_file.file_path}")
                        file = db_file
                        break
        
        if not file:
            return []
        
        # 查找该文件的所有 ranges
        ranges = db.query(CoverageRange).filter(
            CoverageRange.file_id == file.id
        ).all()
        
        # 转换为 CoverageBlock
        blocks = []
        for r in ranges:
            block = CoverageBlock(
                start_line=r.start_line,
                start_col=r.start_col,
                end_line=r.end_line,
                end_col=r.end_col,
                statements=r.statements,
                hit=r.hit
            )
            blocks.append(block)
        
        return blocks
    finally:
        db.close()


def calculate_diff_coverage(
    repo_url: str,
    repo_id: str,
    target_branch: str,
    target_commit: str,
    base_branch: Optional[str] = None
) -> Optional[Dict]:
    """
    计算增量覆盖率
    
    Args:
        repo_url: 仓库 URL
        repo_id: 仓库唯一标识
        target_branch: 目标分支
        target_commit: 目标 commit
        base_branch: 基准分支（可选，默认从配置获取）
    
    Returns:
        Optional[Dict]: 增量覆盖率结果，包含文件列表、总结、Monaco 数据集
    """
    try:
        # 1. 获取基准分支
        if not base_branch:
            base_branch = get_base_branch_for_repo(repo_id)
        
        logger.info(f"Calculating diff coverage: repo_id={repo_id}, target={target_commit}, base_branch={base_branch}")
        
        # 2. 获取仓库路径
        # 使用 bare 仓库路径进行 git 操作
        bare_repo_path = get_bare_repo_path(repo_url)
        if not bare_repo_path:
            logger.error("Failed to get bare repo path")
            return None
        
        # 3. 获取基准 commit
        base_commit = get_base_commit_from_git(bare_repo_path, base_branch, target_commit)
        if not base_commit:
            logger.error("Failed to get base commit")
            return None
        
        logger.info(f"Base commit: {base_commit}")
        
        # 4. 计算 Git Diff
        diff_hunks = parse_git_diff(bare_repo_path, base_commit, target_commit)
        if not diff_hunks:
            logger.warning("No diff hunks found")
            return {
                'files': [],
                'summary': DiffCoverageSummary(
                    total_files=0,
                    total_new_lines=0,
                    new_uncovered_lines=0,
                    new_covered_lines=0,
                    coverage_degraded_lines=0,
                    coverage_improved_lines=0,
                    incremental_coverage_rate=0.0
                ).to_dict(),
                'monaco': {'files': {}},
                'base_commit': base_commit,
                'base_branch': base_branch
            }
        
        logger.info(f"Found {len(diff_hunks)} diff hunks")
        
        # 5. 按文件分组 diff hunks
        file_to_hunks = {}
        for hunk in diff_hunks:
            if hunk.file_path not in file_to_hunks:
                file_to_hunks[hunk.file_path] = []
            file_to_hunks[hunk.file_path].append(hunk)
        
        # 6. 对每个文件，获取覆盖率数据并构建索引
        file_results = []
        for file_path, hunks in file_to_hunks.items():
            # 获取目标 commit 的覆盖率数据，传入repo_url和commit用于路径转换
            target_blocks = get_coverage_blocks_for_file(
                repo_id, 
                target_branch, 
                file_path,
                repo_url=repo_url,
                commit=target_commit
            )
            if not target_blocks:
                logger.warning(f"No coverage data for file: {file_path}")
                continue
            
            # 构建覆盖率索引
            target_coverage_index = build_coverage_index(target_blocks)
            target_coverage_index.file_path = file_path
            
            # 融合 Diff 和 Coverage
            file_result = merge_diff_and_coverage(hunks, target_coverage_index, None)
            file_results.extend(file_result)
        
        # 7. 生成总结
        summary = generate_diff_coverage_summary(file_results)
        
        # 8. 生成 Monaco 数据集
        monaco_data = generate_monaco_dataset(file_results)
        
        # 9. 返回结果
        return {
            'files': [f.to_dict() for f in file_results],
            'summary': summary.to_dict(),
            'monaco': monaco_data,
            'base_commit': base_commit,
            'base_branch': base_branch
        }
    except Exception as e:
        logger.error(f"Failed to calculate diff coverage: {e}")
        return None


def update_base_commit_for_report(report_id: int) -> bool:
    """
    更新报告的基准 commit
    
    Args:
        report_id: 报告 ID
    
    Returns:
        bool: 是否成功
    """
    db = get_db_session()
    try:
        report = db.query(CoverageReport).filter(
            CoverageReport.id == report_id
        ).first()
        
        if not report:
            logger.error(f"Report not found: {report_id}")
            return False
        
        # 获取基准分支
        base_branch = get_base_branch_for_repo(report.repo_id)
        
        # 获取仓库路径
        bare_repo_path = get_bare_repo_path(report.repo)
        if not bare_repo_path:
            logger.error("Failed to get bare repo path")
            return False
        
        # 获取基准 commit
        base_commit = get_base_commit_from_git(bare_repo_path, base_branch, report.commit)
        if not base_commit:
            logger.error("Failed to get base commit")
            return False
        
        # 更新报告
        report.base_branch = base_branch
        report.base_commit = base_commit
        report.updated_at = int(time.time() * 1000)
        
        db.commit()
        logger.info(f"Updated base commit for report {report_id}: {base_commit}")
        return True
    except Exception as e:
        logger.error(f"Failed to update base commit: {e}")
        db.rollback()
        return False
    finally:
        db.close()

