#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增量覆盖率功能使用示例
演示如何在 CI/CD 流程中使用增量覆盖率
"""

import requests
import json
import sys

API_BASE = "http://localhost:8826"


def get_diff_coverage(report_id, base_branch=None):
    """
    获取增量覆盖率数据
    
    Args:
        report_id: 报告 ID
        base_branch: 基准分支（可选）
    
    Returns:
        dict: 增量覆盖率结果
    """
    url = f"{API_BASE}/api/v1/coverage/reports/{report_id}/diff"
    params = {}
    if base_branch:
        params['base_branch'] = base_branch
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_monaco_data(report_id, base_branch=None):
    """
    获取 Monaco 编辑器数据集
    
    Args:
        report_id: 报告 ID
        base_branch: 基准分支（可选）
    
    Returns:
        dict: Monaco 数据集
    """
    url = f"{API_BASE}/api/v1/coverage/reports/{report_id}/monaco"
    params = {}
    if base_branch:
        params['base_branch'] = base_branch
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def set_base_branch(repo_id, base_branch):
    """
    设置仓库的基准分支
    
    Args:
        repo_id: 仓库 ID
        base_branch: 基准分支名
    
    Returns:
        bool: 是否成功
    """
    url = f"{API_BASE}/api/v1/coverage/config/{repo_id}"
    data = {"base_branch": base_branch}
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    result = response.json()
    return result.get('success', False)


def check_incremental_coverage_gate(report_id, threshold=80.0):
    """
    检查增量覆盖率是否达到门禁要求
    
    Args:
        report_id: 报告 ID
        threshold: 增量覆盖率阈值（百分比）
    
    Returns:
        tuple: (是否通过, 增量覆盖率, 详细信息)
    """
    try:
        result = get_diff_coverage(report_id)
        summary = result.get('summary', {})
        
        rate = summary.get('incremental_coverage_rate', 0)
        new_uncovered = summary.get('new_uncovered_lines', 0)
        new_covered = summary.get('new_covered_lines', 0)
        total_files = summary.get('total_files', 0)
        
        passed = rate >= threshold
        
        details = {
            'rate': rate,
            'threshold': threshold,
            'new_uncovered': new_uncovered,
            'new_covered': new_covered,
            'total_files': total_files,
            'base_commit': result.get('base_commit', ''),
            'target_commit': result.get('target_commit', '')
        }
        
        return passed, rate, details
    except Exception as e:
        print(f"Error checking coverage gate: {e}")
        return False, 0, {}


def generate_pr_comment(report_id):
    """
    生成 PR 评论内容
    
    Args:
        report_id: 报告 ID
    
    Returns:
        str: PR 评论 Markdown 文本
    """
    try:
        result = get_diff_coverage(report_id)
        summary = result.get('summary', {})
        
        rate = summary.get('incremental_coverage_rate', 0)
        new_uncovered = summary.get('new_uncovered_lines', 0)
        new_covered = summary.get('new_covered_lines', 0)
        total_files = summary.get('total_files', 0)
        total_new_lines = summary.get('total_new_lines', 0)
        
        # 判断覆盖率等级
        if rate >= 80:
            emoji = "✅"
            level = "优秀"
        elif rate >= 60:
            emoji = "⚠️"
            level = "良好"
        else:
            emoji = "❌"
            level = "较低"
        
        comment = f"""## {emoji} 增量覆盖率报告

### 覆盖率总结
- **增量覆盖率**: {rate:.2f}% ({level})
- **新增代码行**: {total_new_lines} 行
- **已覆盖**: {new_covered} 行 ✅
- **未覆盖**: {new_uncovered} 行 ❌
- **影响文件**: {total_files} 个

### 详细信息
- **基准 Commit**: `{result.get('base_commit', 'N/A')[:8]}`
- **目标 Commit**: `{result.get('target_commit', 'N/A')[:8]}`
- **基准分支**: `{result.get('base_branch', 'N/A')}`

### 文件列表
"""
        
        # 添加文件详情
        files = result.get('files', [])
        for file_data in files[:10]:  # 只显示前10个文件
            file_path = file_data.get('file', '')
            file_summary = file_data.get('summary', {})
            file_new_uncovered = file_summary.get('new_uncovered', 0)
            file_new_covered = file_summary.get('new_covered', 0)
            
            if file_new_uncovered + file_new_covered > 0:
                comment += f"\n- `{file_path}`: {file_new_covered} ✅ / {file_new_uncovered} ❌"
        
        if len(files) > 10:
            comment += f"\n\n*... 还有 {len(files) - 10} 个文件未显示*"
        
        return comment
    except Exception as e:
        return f"⚠️ 生成覆盖率报告失败: {e}"


def example_ci_gate():
    """
    示例：在 CI 中使用增量覆盖率门禁
    """
    print("=" * 60)
    print("示例：增量覆盖率 CI 门禁")
    print("=" * 60)
    
    # 假设从环境变量或 CI 参数获取 report_id
    report_id = 1  # 实际使用时应从参数获取
    threshold = 80.0
    
    print(f"\n检查报告 {report_id} 的增量覆盖率...")
    
    passed, rate, details = check_incremental_coverage_gate(report_id, threshold)
    
    print(f"\n增量覆盖率: {rate:.2f}%")
    print(f"阈值: {threshold}%")
    print(f"新增已覆盖: {details.get('new_covered', 0)} 行")
    print(f"新增未覆盖: {details.get('new_uncovered', 0)} 行")
    print(f"基准 Commit: {details.get('base_commit', '')[:8]}")
    print(f"目标 Commit: {details.get('target_commit', '')[:8]}")
    
    if passed:
        print(f"\n✅ 增量覆盖率达标！")
        return 0
    else:
        print(f"\n❌ 增量覆盖率不足！")
        print(f"需要提升 {threshold - rate:.2f}% 才能达标")
        return 1


def example_pr_comment():
    """
    示例：生成 PR 评论
    """
    print("\n" + "=" * 60)
    print("示例：生成 PR 评论")
    print("=" * 60)
    
    report_id = 1
    
    print(f"\n生成报告 {report_id} 的 PR 评论...\n")
    
    comment = generate_pr_comment(report_id)
    print(comment)


def example_set_base_branch():
    """
    示例：设置基准分支
    """
    print("\n" + "=" * 60)
    print("示例：设置基准分支")
    print("=" * 60)
    
    repo_id = "test-repo-id"
    base_branch = "main"
    
    print(f"\n设置仓库 {repo_id} 的基准分支为 {base_branch}...")
    
    success = set_base_branch(repo_id, base_branch)
    
    if success:
        print(f"✅ 设置成功")
    else:
        print(f"❌ 设置失败")


def example_monaco_integration():
    """
    示例：获取 Monaco 编辑器数据
    """
    print("\n" + "=" * 60)
    print("示例：Monaco 编辑器集成")
    print("=" * 60)
    
    report_id = 1
    
    print(f"\n获取报告 {report_id} 的 Monaco 数据集...\n")
    
    try:
        monaco_data = get_monaco_data(report_id)
        
        print("Monaco 数据结构:")
        print(json.dumps(monaco_data, indent=2, ensure_ascii=False))
        
        print("\n在 Monaco 编辑器中使用示例:")
        print("""
// JavaScript 代码
const monacoData = fetch('/api/v1/coverage/reports/1/monaco')
  .then(res => res.json());

// 为每个文件设置装饰
Object.entries(monacoData.files).forEach(([filePath, fileData]) => {
  Object.entries(fileData.lines).forEach(([lineNumber, lineInfo]) => {
    const decorations = [];
    
    // 根据状态设置不同颜色
    switch(lineInfo.status) {
      case 'new_covered':
        decorations.push({
          range: new monaco.Range(lineNumber, 1, lineNumber, 1),
          options: {
            isWholeLine: true,
            className: 'line-new-covered',  // 绿色背景
            glyphMarginClassName: 'glyph-new-covered'
          }
        });
        break;
      case 'new_uncovered':
        decorations.push({
          range: new monaco.Range(lineNumber, 1, lineNumber, 1),
          options: {
            isWholeLine: true,
            className: 'line-new-uncovered',  // 红色背景
            glyphMarginClassName: 'glyph-new-uncovered'
          }
        });
        break;
      // ... 其他状态
    }
    
    editor.deltaDecorations([], decorations);
  });
});
        """)
    except Exception as e:
        print(f"❌ 获取失败: {e}")


if __name__ == '__main__':
    print("增量覆盖率功能使用示例")
    print("=" * 60)
    print("\n请确保 API 服务已启动: http://localhost:8826\n")
    
    try:
        # 示例1: CI 门禁
        exit_code = example_ci_gate()
        
        # 示例2: PR 评论
        example_pr_comment()
        
        # 示例3: 设置基准分支
        # example_set_base_branch()
        
        # 示例4: Monaco 集成
        # example_monaco_integration()
        
        # 如果是 CI 环境，使用 exit_code 退出
        if '--ci' in sys.argv:
            sys.exit(exit_code)
    
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到 API 服务")
        print("请确保 API 服务已启动: python coverage-api/main.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        sys.exit(1)

