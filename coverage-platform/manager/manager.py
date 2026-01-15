#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
业务逻辑管理层
提供覆盖率报告处理、解析等业务逻辑
"""

import logging
import os
import time
from typing import Dict, List, Optional
from sqlalchemy import func

from models import (
    CoverageReport, CoverageFile, CoverageRange, CoverageConfig,
    get_db_session
)
from manager.repo_manager import clone_or_update_repo


def extract_repo_name(repo_url):
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


def should_exclude_file(file_path, exclude_dirs, exclude_files):
    """
    判断文件是否应该被排除
    
    参数:
        file_path: 文件路径
        exclude_dirs: 排除目录列表，分号分隔的字符串（如 "cmd/;config/"）
        exclude_files: 排除文件后缀列表，分号分隔的字符串（如 "*._test.go;active_test.go"）
    
    返回:
        True: 应该排除
        False: 不应该排除
    """
    if not file_path:
        return False
    
    # 检查排除目录
    if exclude_dirs:
        dirs = [d.strip() for d in exclude_dirs.split(';') if d.strip()]
        for exclude_dir in dirs:
            # 规范化目录路径（确保以/结尾）
            if not exclude_dir.endswith('/'):
                exclude_dir += '/'
            # 检查文件路径是否以排除目录开头
            if file_path.startswith(exclude_dir) or f"/{exclude_dir}" in file_path:
                return True
    
    # 检查排除文件后缀
    if exclude_files:
        files = [f.strip() for f in exclude_files.split(';') if f.strip()]
        for exclude_file in files:
            if exclude_file.startswith('*.'):
                # 通配符模式：匹配后缀
                suffix = exclude_file[1:]  # 去掉 *
                if file_path.endswith(suffix):
                    return True
            else:
                # 全匹配模式
                if file_path.endswith(exclude_file) or file_path.endswith('/' + exclude_file):
                    return True
    
    return False

logger = logging.getLogger(__name__)


# 消息结构
class CoverageReportMessage:
    """覆盖率报告消息结构"""
    def __init__(self, data: dict):
        self.repo = data.get('repo', '')
        self.repo_id = data.get('repo_id', '')
        self.branch = data.get('branch', '')
        self.commit = data.get('commit', '')
        self.ci = data.get('ci', {})
        self.coverage = data.get('coverage', {})
        self.timestamp = data.get('timestamp', 0)


def parse_goc_coverage(raw: str) -> Dict[str, List[Dict]]:
    """
    解析goc格式的覆盖率数据
    goc格式: file.go:startLine.startCol,endLine.endCol statements count
    示例: tuna/api/api.go:10.32,14.34 2 1
    含义: <file>:<startLine>.<startCol>,<endLine>.<endCol> <statements> <count>
    - statements: 该代码块包含的statement数
    - count: 执行次数（mode: count）
    """
    result = {}
    lines = raw.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('mode:'):
            continue
        
        # goc格式: file.go:startLine.startCol,endLine.endCol statements count
        # 按空格分割，得到文件路径+范围、statements和count
        parts = line.split()
        if len(parts) < 3:
            continue
        
        file_path_with_range = parts[0]  # 例如: file.go:10.32,14.34
        statements_str = parts[1]  # 例如: 2
        count_str = parts[2]  # 例如: 1
        
        # 从文件路径+范围中分离出文件路径和范围
        # 找到最后一个冒号的位置
        last_colon_idx = file_path_with_range.rfind(':')
        if last_colon_idx == -1:
            continue
        
        file_path = file_path_with_range[:last_colon_idx]
        range_str = file_path_with_range[last_colon_idx + 1:]  # 例如: 10.32,14.34
        
        # 解析范围: startLine.startCol,endLine.endCol
        range_parts = range_str.split(',')
        if len(range_parts) != 2:
            continue
        
        start_parts = range_parts[0].split('.')
        end_parts = range_parts[1].split('.')
        
        if len(start_parts) != 2 or len(end_parts) != 2:
            continue
        
        try:
            start_line = int(start_parts[0])
            start_col = int(start_parts[1])
            end_line = int(end_parts[0])
            end_col = int(end_parts[1])
            statements = int(statements_str)
            count = int(count_str)
        except ValueError:
            continue
        
        range_item = {
            'start_line': start_line,
            'start_col': start_col,
            'end_line': end_line,
            'end_col': end_col,
            'statements': statements,
            'hit': count  # hit字段存储count（执行次数）
        }
        
        if file_path not in result:
            result[file_path] = []
        result[file_path].append(range_item)
    
    return result


def parse_pyca_coverage(raw: str) -> Dict[str, List[Dict]]:
    """
    解析pyca格式的覆盖率数据（Python覆盖率）
    pyca格式与goc格式相同: file.py:startLine.startCol,endLine.endCol statements count
    示例: file.py:10.0,15.0 6 1
    含义: <file>:<startLine>.<startCol>,<endLine>.<endCol> <statements> <count>
    - statements: 该代码块包含的statement数
    - count: 执行次数（mode: count）
    注意: Python是行级覆盖，所以col通常为0
    """
    # pyca格式与goc格式完全相同，直接复用goc的解析逻辑
    return parse_goc_coverage(raw)


def process_coverage_report(msg: CoverageReportMessage) -> None:
    """
    处理覆盖率报告
    将消息解析并存储到数据库
    对于repo_id+branch相同的数据，更新而不是插入新记录
    对于coverage_files，repo_id+branch+file_path相同的数据，更新updated_at而不是插入
    """
    db = get_db_session()
    try:
        # 开始事务
        now = int(time.time() * 1000)  # 毫秒时间戳
        
        # 检查仓库是否在配置表中
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == msg.repo_id
        ).first()
        
        if not config:
            logger.warning(
                f"Repo not found in config table, skipping: repo_id={msg.repo_id}, "
                f"repo={msg.repo}, branch={msg.branch}, commit={msg.commit}"
            )
            # 不存储覆盖率数据
            return
        
        # 从配置表获取repo_name
        repo_name = config.repo_name
        logger.info(f"Found repo in config: repo_id={msg.repo_id}, repo_name={repo_name}")
        
        # 检查是否存在相同repo_id+branch的报告
        existing_report = db.query(CoverageReport).filter(
            CoverageReport.repo_id == msg.repo_id,
            CoverageReport.branch == msg.branch
        ).first()
        
        if existing_report:
            # 更新现有报告
            logger.info(
                f"Updating existing report: repo_id={msg.repo_id}, repo_name={repo_name}, "
                f"branch={msg.branch}, old_commit={existing_report.commit}, new_commit={msg.commit}"
            )
            report = existing_report
            report.repo_name = repo_name  # 更新 repo_name
            report.commit = msg.commit
            report.ci_provider = msg.ci.get('provider', '')
            report.ci_pipeline_id = msg.ci.get('pipeline_id', '')
            report.ci_job_id = msg.ci.get('job_id', '')
            report.coverage_format = msg.coverage.get('format', 'goc')
            report.coverage_raw = msg.coverage.get('raw', '')
            report.status = 'processing'
            report.updated_at = now
            # created_at保持不变
            # base_branch 和 base_commit 如果为空，保持原值；如果有新值则更新
            # 注意：这里暂不自动计算 base_commit，由后续流程或 API 调用设置
        else:
            # 创建新报告记录
            logger.info(
                f"Creating new report: repo_id={msg.repo_id}, repo_name={repo_name}, "
                f"branch={msg.branch}, commit={msg.commit}"
            )
            
            # 获取基准分支配置
            from manager.diff_manager import get_base_branch_for_repo
            base_branch = get_base_branch_for_repo(msg.repo_id)
            
            report = CoverageReport(
                repo_id=msg.repo_id,
                repo_name=repo_name,  # 存储 repo_name
                branch=msg.branch,
                base_branch=base_branch,  # 设置基准分支
                commit=msg.commit,
                base_commit='',  # 初始为空，后续计算
                ci_provider=msg.ci.get('provider', ''),
                ci_pipeline_id=msg.ci.get('pipeline_id', ''),
                ci_job_id=msg.ci.get('job_id', ''),
                coverage_format=msg.coverage.get('format', 'goc'),
                coverage_raw=msg.coverage.get('raw', ''),
                status='processing',
                created_at=now,
                updated_at=now
            )
            db.add(report)
        
        db.flush()  # 获取ID
        
        # 解析覆盖率数据
        coverage_format = msg.coverage.get('format', 'goc')
        if coverage_format == 'goc':
            try:
                file_coverage = parse_goc_coverage(msg.coverage.get('raw', ''))
            except Exception as e:
                update_now = int(time.time() * 1000)
                report.status = 'failed'
                report.error_message = str(e)
                report.updated_at = update_now
                db.commit()
                raise
        elif coverage_format == 'pyca' or coverage_format == 'pca':  # 支持向后兼容
            try:
                file_coverage = parse_pyca_coverage(msg.coverage.get('raw', ''))
            except Exception as e:
                update_now = int(time.time() * 1000)
                report.status = 'failed'
                report.error_message = str(e)
                report.updated_at = update_now
                db.commit()
                raise
        elif coverage_format == 'jacoco':
            try:
                # jacoco格式与goc格式相同，直接复用goc的解析逻辑
                file_coverage = parse_goc_coverage(msg.coverage.get('raw', ''))
            except Exception as e:
                update_now = int(time.time() * 1000)
                report.status = 'failed'
                report.error_message = str(e)
                report.updated_at = update_now
                db.commit()
                raise
        else:
            err_msg = f"unsupported coverage format: {coverage_format}"
            update_now = int(time.time() * 1000)
            report.status = 'failed'
            report.error_message = err_msg
            report.updated_at = update_now
            db.commit()
            raise ValueError(err_msg)
        
        # 存储文件和数据
        # 在开始处理文件前获取时间戳，用于ranges的created_at
        ranges_timestamp = int(time.time() * 1000)  # 毫秒时间戳
        
        # 获取当前repo_id+branch下的所有文件，用于后续清理不再存在的文件
        existing_files = db.query(CoverageFile).filter(
            CoverageFile.repo_id == report.repo_id,
            CoverageFile.branch == report.branch
        ).all()
        existing_file_paths = {f.file_path: f for f in existing_files}
        processed_file_paths = set()
        
        for file_path, ranges in file_coverage.items():
            processed_file_paths.add(file_path)
            
            # 检查是否存在相同repo_id+branch+file_path的文件
            if file_path in existing_file_paths:
                # 更新现有文件
                file = existing_file_paths[file_path]
                file.updated_at = ranges_timestamp
                # created_at保持不变
                logger.info(f"Updating existing file: {file_path}")
            else:
                # 创建新文件记录
                file = CoverageFile(
                    repo_id=report.repo_id,
                    branch=report.branch,
                    file_path=file_path,
                    created_at=ranges_timestamp,
                    updated_at=ranges_timestamp
                )
                db.add(file)
                logger.info(f"Creating new file: {file_path}")
            
            db.flush()  # 获取ID
            
            # 删除该文件的所有旧ranges
            db.query(CoverageRange).filter(
                CoverageRange.file_id == file.id
            ).delete()
            
            # 创建新的范围记录
            for r in ranges:
                range_obj = CoverageRange(
                    file_id=file.id,
                    start_line=r['start_line'],
                    start_col=r['start_col'],
                    end_line=r['end_line'],
                    end_col=r['end_col'],
                    statements=r['statements'],
                    hit=r['hit'],
                    created_at=ranges_timestamp
                )
                db.add(range_obj)
        
        # 删除不再存在的文件的ranges（可选：也可以保留旧文件，只更新存在的文件）
        # 这里我们选择保留旧文件，只更新存在的文件
        
        # 拉取代码仓库（异步或同步，这里选择同步但可以优化为异步）
        repo_cloned = False
        try:
            logger.info(f"Cloning/updating repository: repo={msg.repo}, repo_id={msg.repo_id}, branch={msg.branch}, commit={msg.commit}")
            success = clone_or_update_repo(msg.repo, msg.repo_id, msg.branch, msg.commit)
            if success:
                logger.info(f"Successfully cloned/updated repository: repo={msg.repo}, commit={msg.commit}")
                repo_cloned = True
            else:
                logger.warning(f"Failed to clone/update repository (returned False): repo={msg.repo}, repo_id={msg.repo_id}, branch={msg.branch}, commit={msg.commit}")
        except Exception as e:
            logger.warning(f"Failed to clone/update repository (exception): {e}, repo={msg.repo}, repo_id={msg.repo_id}, branch={msg.branch}, commit={msg.commit}")
            # 代码拉取失败不影响覆盖率数据的存储
        
        # 如果仓库拉取成功且 base_commit 为空，尝试计算 base_commit
        if repo_cloned and (not report.base_commit or report.base_commit == ''):
            try:
                from manager.diff_manager import get_base_commit_from_git
                from manager.repo_manager import get_bare_repo_path
                
                bare_repo_path = get_bare_repo_path(msg.repo)
                base_branch = report.base_branch or 'master'
                
                logger.info(f"Calculating base commit: repo={msg.repo}, base_branch={base_branch}, target_commit={msg.commit}")
                base_commit = get_base_commit_from_git(bare_repo_path, base_branch, msg.commit)
                
                if base_commit:
                    report.base_commit = base_commit
                    logger.info(f"Set base commit: {base_commit}")
                    
                    # 拉取 base_commit 的代码
                    try:
                        logger.info(f"Cloning base commit code: repo={msg.repo}, base_commit={base_commit}")
                        base_clone_success = clone_or_update_repo(msg.repo, msg.repo_id, base_branch, base_commit)
                        if base_clone_success:
                            logger.info(f"Successfully cloned base commit code: base_commit={base_commit}")
                        else:
                            logger.warning(f"Failed to clone base commit code: base_commit={base_commit}")
                    except Exception as clone_err:
                        logger.warning(f"Failed to clone base commit code: {clone_err}, base_commit={base_commit}")
                        # base_commit 代码拉取失败不影响主流程
                else:
                    logger.warning(f"Failed to calculate base commit")
            except Exception as e:
                logger.warning(f"Failed to calculate base commit: {e}")
                # 计算失败不影响主流程
        
        # 如果 base_commit 已存在（从数据库读取或刚计算出来），确保其代码被拉取
        if repo_cloned and report.base_commit and report.base_commit != '':
            try:
                from manager.repo_manager import get_worktree_dir
                worktree_dir = get_worktree_dir(msg.repo, report.base_commit)
                
                # 检查 base_commit 的 worktree 是否存在
                if not os.path.exists(worktree_dir):
                    logger.info(f"Base commit worktree not found, cloning: base_commit={report.base_commit}")
                    base_branch = report.base_branch or 'master'
                    base_clone_success = clone_or_update_repo(msg.repo, msg.repo_id, base_branch, report.base_commit)
                    if base_clone_success:
                        logger.info(f"Successfully cloned existing base commit code: base_commit={report.base_commit}")
                    else:
                        logger.warning(f"Failed to clone existing base commit code: base_commit={report.base_commit}")
                else:
                    logger.info(f"Base commit worktree already exists: base_commit={report.base_commit}")
            except Exception as e:
                logger.warning(f"Failed to ensure base commit code: {e}, base_commit={report.base_commit}")
                # base_commit 代码拉取失败不影响主流程
        
        # 更新报告状态为完成
        # 使用ranges的时间戳，确保coverage_reports.updated_at和coverage_ranges.created_at一致
        # 这样即使中间有耗时操作（如拉取代码），时间戳也能保持一致
        report.status = 'completed'
        report.updated_at = ranges_timestamp
        
        # 提交事务
        db.commit()
        
        logger.info(
            f"Successfully processed coverage report: repo={msg.repo}, "
            f"repo_id={msg.repo_id}, branch={msg.branch}, commit={msg.commit}"
        )
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def get_report_statistics(report: CoverageReport) -> Dict:
    """
    获取报告的统计信息
    返回总文件数、总statements数、覆盖statements数、覆盖率等
    覆盖率计算规则：
    - count > 0 → 该 block 的所有 statements 都算覆盖
    - count == 0 → 该 block 的所有 statements 都未覆盖
    注意：统计时会根据配置排除指定的目录和文件
    """
    db = get_db_session()
    try:
        # 获取仓库配置（用于排除目录和文件）
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == report.repo_id
        ).first()
        
        exclude_dirs = config.exclude_dirs if config else ''
        exclude_files = config.exclude_files if config else ''
        
        # 查询该报告下的所有文件（通过repo_id和branch查询）
        files = db.query(CoverageFile).filter(
            CoverageFile.repo_id == report.repo_id,
            CoverageFile.branch == report.branch
        ).all()
        
        # 计算统计信息
        total_files = 0
        total_statements = 0
        covered_statements = 0
        
        for file in files:
            # 检查文件是否应该被排除
            if should_exclude_file(file.file_path, exclude_dirs, exclude_files):
                logger.debug(f"Excluding file from statistics: {file.file_path}")
                continue
            
            total_files += 1
            
            # 查询该文件的所有 ranges
            file_ranges = db.query(CoverageRange).filter(
                CoverageRange.file_id == file.id
            ).all()
            
            # 计算该文件的总statements数和已覆盖statements数
            for r in file_ranges:
                # 累加总statements数
                total_statements += r.statements
                
                # 如果该 range 被覆盖（hit > 0），则累加该range的statements数
                if r.hit > 0:
                    covered_statements += r.statements
        
        coverage_rate = 0.0
        if total_statements > 0:
            coverage_rate = (covered_statements / total_statements) * 100
        
        return {
            'total_files': total_files,
            'total_statements': total_statements,
            'covered_statements': covered_statements,
            'coverage_rate': coverage_rate
        }
    finally:
        db.close()


def get_file_summary(file: CoverageFile) -> Optional[Dict]:
    """
    获取文件的统计摘要
    返回总statements数、覆盖statements数、覆盖率等
    覆盖率计算规则：
    - count > 0 → 该 block 的所有 statements 都算覆盖
    - count == 0 → 该 block 的所有 statements 都未覆盖
    注意：如果文件应该被排除，返回None
    """
    db = get_db_session()
    try:
        # 获取仓库配置（用于排除目录和文件）
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_id == file.repo_id
        ).first()
        
        exclude_dirs = config.exclude_dirs if config else ''
        exclude_files = config.exclude_files if config else ''
        
        # 检查文件是否应该被排除
        if should_exclude_file(file.file_path, exclude_dirs, exclude_files):
            logger.debug(f"Excluding file from summary: {file.file_path}")
            return None
        
        # 查询所有 ranges
        all_ranges = db.query(CoverageRange).filter(
            CoverageRange.file_id == file.id
        ).all()
        
        # 计算总statements数和已覆盖statements数
        total_statements = 0
        covered_statements = 0
        
        for r in all_ranges:
            # 累加总statements数
            total_statements += r.statements
            
            # 如果该 range 被覆盖（hit > 0），则累加该range的statements数
            if r.hit > 0:
                covered_statements += r.statements
        
        coverage_rate = 0.0
        if total_statements > 0:
            coverage_rate = (covered_statements / total_statements) * 100
        
        return {
            'id': file.id,
            'repo_id': file.repo_id,
            'branch': file.branch,
            'file': file.file_path,
            'total_statements': total_statements,
            'covered_statements': covered_statements,
            'coverage_rate': coverage_rate,
            'created_at': file.created_at
        }
    finally:
        db.close()

