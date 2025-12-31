#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复脚本：为现有报告补拉取 base_commit 的代码
用于解决之前consumer没有拉取base_commit代码的问题
"""

import sys
import os
import logging

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import CoverageReport, get_db_session
from manager.repo_manager import clone_or_update_repo, get_worktree_dir

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_missing_worktrees():
    """为所有报告补拉取缺失的commit和base_commit代码"""
    db = get_db_session()
    
    try:
        # 查询所有报告
        reports = db.query(CoverageReport).all()
        logger.info(f"找到 {len(reports)} 个覆盖率报告")
        
        total_commits = 0
        missing_commits = 0
        fixed_commits = 0
        failed_commits = 0
        
        for report in reports:
            logger.info(f"\n处理报告 ID={report.id}, repo={report.repo_url}, commit={report.commit}")
            
            # 检查并拉取当前commit的代码
            if report.commit:
                total_commits += 1
                worktree_dir = get_worktree_dir(report.repo_url, report.commit)
                
                if not os.path.exists(worktree_dir):
                    logger.warning(f"  ⚠️  当前commit的worktree不存在: {report.commit}")
                    missing_commits += 1
                    
                    # 尝试拉取
                    logger.info(f"  🔄 正在拉取commit代码...")
                    try:
                        success = clone_or_update_repo(
                            report.repo_url,
                            report.repo_id,
                            report.branch,
                            report.commit
                        )
                        if success:
                            logger.info(f"  ✅ 成功拉取commit代码: {report.commit}")
                            fixed_commits += 1
                        else:
                            logger.error(f"  ❌ 拉取commit代码失败: {report.commit}")
                            failed_commits += 1
                    except Exception as e:
                        logger.error(f"  ❌ 拉取commit代码异常: {e}")
                        failed_commits += 1
                else:
                    logger.info(f"  ✅ 当前commit的worktree已存在: {report.commit}")
            
            # 检查并拉取base_commit的代码
            if report.base_commit and report.base_commit != '':
                total_commits += 1
                worktree_dir = get_worktree_dir(report.repo_url, report.base_commit)
                
                if not os.path.exists(worktree_dir):
                    logger.warning(f"  ⚠️  base_commit的worktree不存在: {report.base_commit}")
                    missing_commits += 1
                    
                    # 尝试拉取
                    logger.info(f"  🔄 正在拉取base_commit代码...")
                    try:
                        base_branch = report.base_branch or 'master'
                        success = clone_or_update_repo(
                            report.repo_url,
                            report.repo_id,
                            base_branch,
                            report.base_commit
                        )
                        if success:
                            logger.info(f"  ✅ 成功拉取base_commit代码: {report.base_commit}")
                            fixed_commits += 1
                        else:
                            logger.error(f"  ❌ 拉取base_commit代码失败: {report.base_commit}")
                            failed_commits += 1
                    except Exception as e:
                        logger.error(f"  ❌ 拉取base_commit代码异常: {e}")
                        failed_commits += 1
                else:
                    logger.info(f"  ✅ base_commit的worktree已存在: {report.base_commit}")
            else:
                logger.info(f"  ℹ️  报告没有base_commit")
        
        # 输出统计信息
        logger.info(f"\n" + "="*60)
        logger.info(f"修复完成统计:")
        logger.info(f"  总报告数: {len(reports)}")
        logger.info(f"  总commit数: {total_commits}")
        logger.info(f"  缺失worktree数: {missing_commits}")
        logger.info(f"  成功修复数: {fixed_commits}")
        logger.info(f"  修复失败数: {failed_commits}")
        logger.info(f"="*60)
        
    except Exception as e:
        logger.error(f"修复过程出错: {e}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    logger.info("开始修复缺失的worktrees...")
    logger.info("="*60)
    
    try:
        fix_missing_worktrees()
        logger.info("\n✅ 修复脚本执行完成！")
    except KeyboardInterrupt:
        logger.info("\n用户中断")
    except Exception as e:
        logger.error(f"\n❌ 修复脚本执行失败: {e}")
        sys.exit(1)

