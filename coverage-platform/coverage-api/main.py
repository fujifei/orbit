#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import os

# 添加父目录到路径，以便导入共享模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import func, text

from models import (
    CoverageReport, CoverageFile, CoverageRange, CoverageConfig,
    get_db_session, close_db_session, init_db
)
from manager.manager import get_report_statistics, get_file_summary
from manager.repo_manager import get_file_content
from manager.diff_manager import (
    get_base_branch_for_repo, set_base_branch_for_repo,
    calculate_diff_coverage, update_base_commit_for_report
)
from manager.config_manager import (
    get_all_configs as get_all_configs_logic,
    get_config_by_repo_id as get_config_by_id_logic,
    get_repo_config_with_default,
    create_config as create_config_logic,
    update_config as update_config_logic,
    delete_config as delete_config_logic,
    set_repo_config as set_repo_config_logic,
    get_repo_id_from_url as get_repo_id_from_url_logic
)
import time
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)
CORS(app)


# 获取数据库会话
def get_db():
    return get_db_session()


# 关闭数据库会话
@app.teardown_appcontext
def close_db(error):
    close_db_session()




# 健康检查端点
@app.route('/health', methods=['GET'])
def health():
    try:
        db = get_db()
        db.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


# 获取覆盖率报告列表
@app.route('/api/v1/coverage/reports', methods=['GET'])
def get_coverage_reports():
    logger.info("Received request: GET /api/v1/coverage/reports")
    
    try:
        db = get_db()
        
        # 构建查询
        query = db.query(CoverageReport)
        count_query = db.query(func.count(CoverageReport.id))
        
        # 支持按仓库名称模糊搜索（直接搜索 repo_name 字段）
        if repo := request.args.get('repo'):
            query = query.filter(CoverageReport.repo_name.like(f'%{repo}%'))
            count_query = count_query.filter(CoverageReport.repo_name.like(f'%{repo}%'))
        
        # 支持按分支模糊搜索
        if branch := request.args.get('branch'):
            query = query.filter(CoverageReport.branch.like(f'%{branch}%'))
            count_query = count_query.filter(CoverageReport.branch.like(f'%{branch}%'))
        
        # 支持按状态过滤
        if status := request.args.get('status'):
            query = query.filter(CoverageReport.status == status)
            count_query = count_query.filter(CoverageReport.status == status)
        
        # 支持创建时间范围搜索
        if created_at_start := request.args.get('created_at_start'):
            try:
                created_at_start_ts = int(created_at_start)
                query = query.filter(CoverageReport.created_at >= created_at_start_ts)
                count_query = count_query.filter(CoverageReport.created_at >= created_at_start_ts)
            except ValueError:
                pass
        
        if created_at_end := request.args.get('created_at_end'):
            try:
                created_at_end_ts = int(created_at_end)
                query = query.filter(CoverageReport.created_at <= created_at_end_ts)
                count_query = count_query.filter(CoverageReport.created_at <= created_at_end_ts)
            except ValueError:
                pass
        
        # 支持更新时间范围搜索
        if updated_at_start := request.args.get('updated_at_start'):
            try:
                updated_at_start_ts = int(updated_at_start)
                query = query.filter(CoverageReport.updated_at >= updated_at_start_ts)
                count_query = count_query.filter(CoverageReport.updated_at >= updated_at_start_ts)
            except ValueError:
                pass
        
        if updated_at_end := request.args.get('updated_at_end'):
            try:
                updated_at_end_ts = int(updated_at_end)
                query = query.filter(CoverageReport.updated_at <= updated_at_end_ts)
                count_query = count_query.filter(CoverageReport.updated_at <= updated_at_end_ts)
            except ValueError:
                pass
        
        # 分页支持
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        offset = (page - 1) * page_size
        
        logger.info("Counting total reports...")
        total = count_query.scalar()
        logger.info(f"Total reports: {total}")
        
        # 按创建时间倒序排列
        query = query.order_by(CoverageReport.created_at.desc())
        
        logger.info(f"Querying reports (offset: {offset}, limit: {page_size})...")
        reports = query.offset(offset).limit(page_size).all()
        logger.info(f"Found {len(reports)} reports")
        
        # 批量查询配置信息
        repo_ids = [r.repo_id for r in reports]
        configs = db.query(CoverageConfig).filter(CoverageConfig.repo_id.in_(repo_ids)).all()
        config_map = {c.repo_id: c for c in configs}
        
        # 批量计算每个报告的统计信息
        report_dicts = []
        for report in reports:
            # 获取配置信息
            config = config_map.get(report.repo_id)
            
            # 转换为字典，包含仓库信息
            report_dict = report.to_dict(config=config)
            
            # 计算全量覆盖率数据
            statistics = get_report_statistics(report)
            report_dict['total_statements'] = statistics['total_statements']
            report_dict['covered_statements'] = statistics['covered_statements']
            report_dict['coverage_rate'] = statistics['coverage_rate']
            
            # 添加基准分支和基准 commit（用于增量覆盖率）
            if not report_dict.get('base_branch'):
                report_dict['base_branch'] = get_base_branch_for_repo(report.repo_id)
            
            report_dicts.append(report_dict)
        
        return jsonify({
            'data': report_dicts,
            'total': total,
            'page': page,
            'page_size': page_size
        }), 200
    except Exception as e:
        logger.error(f"Error querying coverage reports: {e}")
        return jsonify({
            'error': 'Failed to query coverage reports',
            'detail': str(e)
        }), 500


# 获取覆盖率报告详情
@app.route('/api/v1/coverage/reports/<int:report_id>', methods=['GET'])
def get_coverage_report_detail(report_id):
    try:
        db = get_db()
        
        # 查询报告
        report = db.query(CoverageReport).filter(CoverageReport.id == report_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # 获取配置信息
        config = db.query(CoverageConfig).filter(CoverageConfig.repo_id == report.repo_id).first()
        
        # 获取统计信息
        statistics = get_report_statistics(report)
        
        # 查询该报告下的所有文件（通过repo_id和branch查询）
        files = db.query(CoverageFile).filter(
            CoverageFile.repo_id == report.repo_id,
            CoverageFile.branch == report.branch
        ).all()
        
        return jsonify({
            'report': report.to_dict(config=config),
            'statistics': statistics,
            'files': [file.to_dict() for file in files]
        }), 200
    except Exception as e:
        logger.error(f"Error getting report detail: {e}")
        return jsonify({'error': str(e)}), 500


# 获取覆盖率文件列表
@app.route('/api/v1/coverage/files', methods=['GET'])
def get_coverage_files():
    try:
        db = get_db()
        
        # 构建查询
        query = db.query(CoverageFile)
        
        # 支持按report_id过滤（通过report_id查找对应的repo_id和branch）
        if report_id := request.args.get('report_id'):
            try:
                report_id_int = int(report_id)
                report = db.query(CoverageReport).filter(CoverageReport.id == report_id_int).first()
                if report:
                    query = query.filter(
                        CoverageFile.repo_id == report.repo_id,
                        CoverageFile.branch == report.branch
                    )
                else:
                    # 如果报告不存在，返回空列表
                    return jsonify({
                        'data': [],
                        'total': 0
                    }), 200
            except ValueError:
                return jsonify({
                    'error': 'Invalid report_id'
                }), 400
        
        # 支持按repo_id和branch过滤
        if repo_id := request.args.get('repo_id'):
            query = query.filter(CoverageFile.repo_id == repo_id)
        if branch := request.args.get('branch'):
            query = query.filter(CoverageFile.branch == branch)
        
        # 查询所有文件
        files = query.all()
        
        # 计算每个文件的统计信息（过滤掉被排除的文件）
        summaries = []
        for file in files:
            summary = get_file_summary(file)
            if summary is not None:  # 排除被配置排除的文件
                summaries.append(summary)
        
        return jsonify({
            'data': summaries,
            'total': len(summaries)
        }), 200
    except Exception as e:
        logger.error(f"Error querying coverage files: {e}")
        return jsonify({
            'error': 'Failed to query coverage files',
            'detail': str(e)
        }), 500


# 获取覆盖率文件详情
@app.route('/api/v1/coverage/files/<int:file_id>', methods=['GET'])
def get_coverage_file_detail(file_id):
    try:
        db = get_db()
        
        # 查询文件
        file = db.query(CoverageFile).filter(CoverageFile.id == file_id).first()
        if not file:
            return jsonify({'error': 'File not found'}), 404
        
        # 获取文件统计摘要（包含statements信息）
        file_summary = get_file_summary(file)
        
        # 查询该文件的所有ranges（按start_line和start_col排序以确保一致性）
        ranges = db.query(CoverageRange).filter(
            CoverageRange.file_id == file.id
        ).order_by(CoverageRange.start_line, CoverageRange.start_col).all()
        
        # 记录查询到的ranges数量，用于调试
        logger.debug(f"Querying ranges for file_id={file_id}, found {len(ranges)} ranges")
        
        # 检查22-26行的ranges（用于调试）
        ranges_22_26 = [r for r in ranges if r.start_line <= 26 and r.end_line >= 22]
        if ranges_22_26:
            logger.debug(f"Found {len(ranges_22_26)} ranges covering lines 22-26: {[(r.start_line, r.end_line, r.hit) for r in ranges_22_26]}")
        
        # 返回符合前端要求的格式，包含statements统计信息
        return jsonify({
            'file': file.file_path,
            'ranges': [r.to_dict() for r in ranges],
            'total_statements': file_summary['total_statements'],
            'covered_statements': file_summary['covered_statements'],
            'coverage_rate': file_summary['coverage_rate']
        }), 200
    except Exception as e:
        logger.error(f"Error getting file detail: {e}")
        return jsonify({'error': str(e)}), 500


# 获取文件内容
@app.route('/api/coverage/file', methods=['GET'])
def get_file_content_api():
    """
    获取文件内容
    参数:
        repo: 仓库名称（如tuna），用于查找repo URL
        commit: commit hash
        path: 文件路径（相对于仓库根目录）
    """
    try:
        repo_name = request.args.get('repo')
        commit = request.args.get('commit')
        file_path = request.args.get('path')
        
        if not repo_name or not commit or not file_path:
            return jsonify({
                'error': 'Missing required parameters: repo, commit, path'
            }), 400
        
        db = get_db()
        
        # 通过repo名称从配置表查找repo URL
        config = db.query(CoverageConfig).filter(
            CoverageConfig.repo_name.like(f'%{repo_name}%')
        ).first()
        
        if not config:
            return jsonify({
                'error': f'Repository not found: {repo_name}'
            }), 404
        
        repo_url = config.repo_url
        
        # 获取文件内容
        content = get_file_content(repo_url, commit, file_path)
        
        if content is None:
            return jsonify({
                'error': f'File not found: {file_path}'
            }), 404
        
        return jsonify({
            'content': content,
            'repo': repo_name,
            'repo_url': repo_url,
            'commit': commit,
            'path': file_path
        }), 200
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return jsonify({'error': str(e)}), 500


# 获取增量覆盖率数据
@app.route('/api/v1/coverage/reports/<int:report_id>/diff', methods=['GET'])
def get_diff_coverage(report_id):
    """
    获取增量覆盖率数据
    
    参数:
        report_id: 报告 ID
        base_branch: 基准分支（可选，默认从配置获取）
    """
    try:
        db = get_db()
        
        # 查询报告
        report = db.query(CoverageReport).filter(CoverageReport.id == report_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # 获取配置信息
        config = db.query(CoverageConfig).filter(CoverageConfig.repo_id == report.repo_id).first()
        if not config:
            return jsonify({'error': 'Config not found for this repo'}), 404
        
        # 获取基准分支（优先使用参数，否则使用配置）
        base_branch = request.args.get('base_branch')
        if not base_branch:
            base_branch = get_base_branch_for_repo(report.repo_id)
        
        # 计算增量覆盖率
        logger.info(f"Calculating diff coverage for report {report_id}")
        diff_result = calculate_diff_coverage(
            repo_url=config.repo_url,
            repo_id=report.repo_id,
            target_branch=report.branch,
            target_commit=report.commit,
            base_branch=base_branch
        )
        
        if not diff_result:
            return jsonify({
                'error': 'Failed to calculate diff coverage'
            }), 500
        
        # 更新报告的 base_commit（如果尚未设置）
        if not report.base_commit and diff_result.get('base_commit'):
            report.base_commit = diff_result['base_commit']
            report.base_branch = diff_result['base_branch']
            report.updated_at = int(__import__('time').time() * 1000)
            db.commit()
        
        return jsonify({
            'report_id': report_id,
            'target_commit': report.commit,
            'base_commit': diff_result['base_commit'],
            'base_branch': diff_result['base_branch'],
            'files': diff_result['files'],
            'summary': diff_result['summary']
        }), 200
    except Exception as e:
        logger.error(f"Error getting diff coverage: {e}")
        return jsonify({'error': str(e)}), 500


# 获取 Monaco 编辑器数据
@app.route('/api/v1/coverage/reports/<int:report_id>/monaco', methods=['GET'])
def get_monaco_data(report_id):
    """
    获取 Monaco 编辑器用的最小数据集
    
    参数:
        report_id: 报告 ID
        base_branch: 基准分支（可选）
    """
    try:
        db = get_db()
        
        # 查询报告
        report = db.query(CoverageReport).filter(CoverageReport.id == report_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # 获取配置信息
        config = db.query(CoverageConfig).filter(CoverageConfig.repo_id == report.repo_id).first()
        if not config:
            return jsonify({'error': 'Config not found for this repo'}), 404
        
        # 获取基准分支
        base_branch = request.args.get('base_branch')
        if not base_branch:
            base_branch = get_base_branch_for_repo(report.repo_id)
        
        # 计算增量覆盖率
        diff_result = calculate_diff_coverage(
            repo_url=config.repo_url,
            repo_id=report.repo_id,
            target_branch=report.branch,
            target_commit=report.commit,
            base_branch=base_branch
        )
        
        if not diff_result:
            return jsonify({
                'error': 'Failed to calculate diff coverage'
            }), 500
        
        return jsonify(diff_result['monaco']), 200
    except Exception as e:
        logger.error(f"Error getting monaco data: {e}")
        return jsonify({'error': str(e)}), 500


# 获取仓库配置
@app.route('/api/v1/coverage/config/<repo_id>', methods=['GET'])
def get_repo_config(repo_id):
    """
    获取仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    """
    try:
        result = get_repo_config_with_default(repo_id)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting repo config: {e}")
        return jsonify({'error': str(e)}), 500


# 设置仓库配置
@app.route('/api/v1/coverage/config/<repo_id>', methods=['POST'])
def set_repo_config(repo_id):
    """
    设置仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    
    请求体:
        {
            "base_branch": "master"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        base_branch = data.get('base_branch')
        if not base_branch:
            return jsonify({'error': 'Missing base_branch'}), 400
        
        # 设置配置
        success = set_repo_config_logic(repo_id, base_branch)
        if not success:
            return jsonify({'error': 'Failed to set config'}), 500
        
        return jsonify({
            'success': True,
            'repo_id': repo_id,
            'base_branch': base_branch
        }), 200
    except Exception as e:
        logger.error(f"Error setting repo config: {e}")
        return jsonify({'error': str(e)}), 500


# 更新报告的基准 commit
@app.route('/api/v1/coverage/reports/<int:report_id>/base-commit', methods=['POST'])
def update_report_base_commit(report_id):
    """
    更新报告的基准 commit
    
    参数:
        report_id: 报告 ID
    """
    try:
        success = update_base_commit_for_report(report_id)
        if not success:
            return jsonify({'error': 'Failed to update base commit'}), 500
        
        return jsonify({
            'success': True,
            'report_id': report_id
        }), 200
    except Exception as e:
        logger.error(f"Error updating base commit: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== Config Management APIs ====================

# 获取所有仓库配置列表
@app.route('/api/v1/coverage/configs', methods=['GET'])
def get_all_configs():
    """
    获取所有仓库配置列表
    
    查询参数:
        repo_name: 仓库名称（可选，模糊搜索）
        repo_type: 仓库类型（可选，1=go, 2=python, 3=java）
    """
    try:
        repo_name = request.args.get('repo_name')
        repo_type = request.args.get('repo_type')
        
        # 转换 repo_type 为整数（如果提供）
        repo_type_int = None
        if repo_type is not None:
            try:
                repo_type_int = int(repo_type)
            except ValueError:
                return jsonify({'error': 'Invalid repo_type, must be an integer'}), 400
        
        result = get_all_configs_logic(repo_name=repo_name, repo_type=repo_type_int)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting configs: {e}")
        return jsonify({'error': str(e)}), 500


# 获取单个仓库配置
@app.route('/api/v1/coverage/configs/<repo_id>', methods=['GET'])
def get_config_by_repo_id(repo_id):
    """
    获取单个仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    """
    try:
        result = get_config_by_id_logic(repo_id)
        if not result:
            return jsonify({'error': 'Config not found'}), 404
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': str(e)}), 500


# 创建仓库配置
@app.route('/api/v1/coverage/configs', methods=['POST'])
def create_config():
    """
    创建仓库配置
    
    请求体:
        {
            "repo_url": "https://github.com/fujifei/tuna.git",
            "repo_id": "xxxxx",
            "repo_type": 1,
            "base_branch": "master",
            "exclude_dirs": "cmd/;config/",
            "exclude_files": "*._test.go;active_test.go"
        }
    
    注意: 
        - repo_name 会自动从 repo_url 中提取
        - repo_type: 1=go语言, 2=python语言, 3=java语言（默认1）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        repo_url = data.get('repo_url', '')
        repo_id = data.get('repo_id', '')
        repo_type = data.get('repo_type', 1)  # 默认值为1（go语言）
        base_branch = data.get('base_branch', 'master')
        exclude_dirs = data.get('exclude_dirs', '')
        exclude_files = data.get('exclude_files', '')
        
        # 验证 repo_type
        if repo_type not in [1, 2, 3]:
            return jsonify({'error': 'Invalid repo_type, must be 1 (go), 2 (python), or 3 (java)'}), 400
        
        result = create_config_logic(
            repo_url=repo_url,
            repo_id=repo_id,
            base_branch=base_branch,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
            repo_type=repo_type
        )
        
        return jsonify({
            'success': True,
            'data': result
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating config: {e}")
        return jsonify({'error': str(e)}), 500


# 更新仓库配置
@app.route('/api/v1/coverage/configs/<repo_id>', methods=['PUT'])
def update_config(repo_id):
    """
    更新仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    
    请求体:
        {
            "base_branch": "master",
            "exclude_dirs": "cmd/;config/",
            "exclude_files": "*._test.go;active_test.go"
        }
    
    注意: repo_url 和 repo_name 不可修改
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        base_branch = data.get('base_branch')
        exclude_dirs = data.get('exclude_dirs')
        exclude_files = data.get('exclude_files')
        
        result = update_config_logic(
            repo_id=repo_id,
            base_branch=base_branch,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files
        )
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({'error': str(e)}), 500


# 删除仓库配置
@app.route('/api/v1/coverage/configs/<repo_id>', methods=['DELETE'])
def delete_config(repo_id):
    """
    删除仓库配置
    
    参数:
        repo_id: 仓库唯一标识
    """
    try:
        delete_config_logic(repo_id)
        return jsonify({
            'success': True,
            'message': 'Config deleted successfully'
        }), 200
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting config: {e}")
        return jsonify({'error': str(e)}), 500


# 根据仓库URL获取RepoID
@app.route('/api/v1/coverage/configs/repo-id', methods=['POST'])
def get_repo_id():
    """
    根据仓库URL获取RepoID
    
    请求体:
        {
            "repo_url": "https://github.com/fujifei/tuna.git"
            或
            "repo_url": "git@github.com:fujifei/tuna.git"
        }
    
    返回:
        {
            "success": true,
            "data": {
                "repo_id": "github.com/fujifei/tuna"
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        repo_url = data.get('repo_url', '')
        if not repo_url:
            return jsonify({'error': 'Missing repo_url'}), 400
        
        repo_id = get_repo_id_from_url_logic(repo_url)
        
        return jsonify({
            'success': True,
            'data': {
                'repo_id': repo_id  # 现在是整数
            }
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error getting repo_id: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    init_db()
    
    logger.info("Server starting on :8826")
    app.run(host='0.0.0.0', port=8826, debug=False)
