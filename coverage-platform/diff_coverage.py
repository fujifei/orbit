#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增量覆盖率模块
提供 Git Diff 计算、Coverage 索引构建、Diff + Coverage 融合等功能
"""

import logging
import subprocess
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DiffCoverageStatus(Enum):
    """增量覆盖率状态枚举"""
    NEW_UNCOVERED = "new_uncovered"  # 新增未覆盖
    NEW_COVERED = "new_covered"  # 新增已覆盖
    COVERAGE_DEGRADED = "coverage_degraded"  # 覆盖退化（原来覆盖，现在不覆盖）
    COVERAGE_IMPROVED = "coverage_improved"  # 覆盖提升（原来不覆盖，现在覆盖）


@dataclass
class LineInfo:
    """行级信息"""
    line_number: int
    content: str


@dataclass
class DiffHunk:
    """Diff 代码块"""
    file_path: str
    old_start: int  # 旧文件起始行号
    old_count: int  # 旧文件行数
    new_start: int  # 新文件起始行号
    new_count: int  # 新文件行数
    added_lines: List[int]  # 新增的行号列表
    deleted_lines: List[int]  # 删除的行号列表（旧文件的行号）
    modified_lines: List[int]  # 修改的行号列表（新文件的行号）


@dataclass
class CoverageBlock:
    """覆盖率原子单元（对应数据库中的 CoverageRange）"""
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    statements: int
    hit: int  # 执行次数
    
    def is_covered(self) -> bool:
        """判断是否被覆盖"""
        return self.hit > 0
    
    def covers_line(self, line_number: int) -> bool:
        """判断是否覆盖指定行"""
        return self.start_line <= line_number <= self.end_line


@dataclass
class CoverageIndex:
    """覆盖率索引（按行号快速查找覆盖率信息）"""
    file_path: str
    line_to_blocks: Dict[int, List[CoverageBlock]]  # 行号 -> 覆盖该行的所有 blocks
    
    def get_line_coverage(self, line_number: int) -> Optional[bool]:
        """
        获取指定行的覆盖状态
        返回 True（已覆盖）、False（未覆盖）、None（不可覆盖/没有覆盖率数据）
        """
        if line_number not in self.line_to_blocks:
            return None
        
        blocks = self.line_to_blocks[line_number]
        if not blocks:
            return None
        
        # 如果有任何一个 block 被覆盖，则认为该行被覆盖
        for block in blocks:
            if block.is_covered():
                return True
        
        # 所有 block 都未覆盖
        return False
    
    def get_line_hit_count(self, line_number: int) -> int:
        """获取指定行的执行次数（取所有 block 的最大值）"""
        if line_number not in self.line_to_blocks:
            return 0
        
        blocks = self.line_to_blocks[line_number]
        if not blocks:
            return 0
        
        return max(block.hit for block in blocks)


@dataclass
class DiffCoverageLine:
    """Diff + Coverage 融合结果（单行）"""
    line_number: int
    status: DiffCoverageStatus
    hit_count: int  # 执行次数
    is_new: bool  # 是否为新增行
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'line': self.line_number,
            'status': self.status.value,
            'hit': self.hit_count,
            'is_new': self.is_new
        }


@dataclass
class DiffCoverageFile:
    """文件级别的 Diff + Coverage 融合结果"""
    file_path: str
    lines: List[DiffCoverageLine]
    
    # 统计信息
    new_uncovered_count: int = 0
    new_covered_count: int = 0
    coverage_degraded_count: int = 0
    coverage_improved_count: int = 0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'file': self.file_path,
            'lines': [line.to_dict() for line in self.lines],
            'summary': {
                'new_uncovered': self.new_uncovered_count,
                'new_covered': self.new_covered_count,
                'coverage_degraded': self.coverage_degraded_count,
                'coverage_improved': self.coverage_improved_count
            }
        }


@dataclass
class DiffCoverageSummary:
    """增量覆盖率总结（用于 PR Gate）"""
    total_files: int
    total_new_lines: int
    new_uncovered_lines: int
    new_covered_lines: int
    coverage_degraded_lines: int
    coverage_improved_lines: int
    incremental_coverage_rate: float  # 增量覆盖率 = new_covered / (new_covered + new_uncovered)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'total_files': self.total_files,
            'total_new_lines': self.total_new_lines,
            'new_uncovered_lines': self.new_uncovered_lines,
            'new_covered_lines': self.new_covered_lines,
            'coverage_degraded_lines': self.coverage_degraded_lines,
            'coverage_improved_lines': self.coverage_improved_lines,
            'incremental_coverage_rate': self.incremental_coverage_rate
        }


def parse_git_diff(repo_path: str, base_commit: str, target_commit: str) -> List[DiffHunk]:
    """
    解析 Git Diff，获取行级差异
    
    Args:
        repo_path: 仓库本地路径
        base_commit: 基准 commit
        target_commit: 目标 commit
    
    Returns:
        List[DiffHunk]: Diff 代码块列表
    """
    try:
        # 执行 git diff 命令，获取 unified diff 格式
        # -U0: 不显示上下文行
        # -M: 检测文件重命名（避免将重命名识别为删除+新增）
        cmd = ['git', 'diff', '-U0', '-M', f'{base_commit}...{target_commit}']
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Git diff failed: {result.stderr}")
            return []
        
        diff_output = result.stdout
        return _parse_unified_diff(diff_output)
    except subprocess.TimeoutExpired:
        logger.error(f"Git diff timeout: {base_commit}...{target_commit}")
        return []
    except Exception as e:
        logger.error(f"Error parsing git diff: {e}")
        return []


def _parse_unified_diff(diff_output: str) -> List[DiffHunk]:
    """
    解析 unified diff 格式的输出
    
    格式示例:
    diff --git a/file.go b/file.go
    index abc123..def456 100644
    --- a/file.go
    +++ b/file.go
    @@ -10,3 +10,4 @@ ...
    -deleted line
    +added line
    """
    hunks = []
    current_file = None
    lines = diff_output.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 解析文件路径
        if line.startswith('diff --git'):
            # diff --git a/file.go b/file.go
            # parts[2] 是旧文件路径 (a/xxx), parts[3] 是新文件路径 (b/xxx)
            # 我们需要新文件路径来匹配覆盖率数据
            parts = line.split()
            if len(parts) >= 4:
                # 去掉 b/ 前缀，使用新文件路径
                # 注意：不能用 lstrip，因为它会移除所有 'b' 和 '/' 字符
                new_file_path = parts[3]
                if new_file_path.startswith('b/'):
                    current_file = new_file_path[2:]  # 去掉前两个字符 "b/"
                else:
                    current_file = new_file_path
        
        # 解析 hunk 头
        elif line.startswith('@@'):
            if not current_file:
                i += 1
                continue
            
            # @@ -10,3 +10,4 @@ ...
            # 提取行号信息
            try:
                header = line.split('@@')[1].strip()
                parts = header.split()
                
                # 解析旧文件范围 -10,3
                old_range = parts[0].lstrip('-').split(',')
                old_start = int(old_range[0])
                old_count = int(old_range[1]) if len(old_range) > 1 else 1
                
                # 解析新文件范围 +10,4
                new_range = parts[1].lstrip('+').split(',')
                new_start = int(new_range[0])
                new_count = int(new_range[1]) if len(new_range) > 1 else 1
                
                # 解析 hunk 内容
                added_lines = []
                deleted_lines = []
                modified_lines = []
                
                new_line_num = new_start
                old_line_num = old_start
                
                i += 1
                while i < len(lines):
                    content_line = lines[i]
                    
                    # 遇到下一个 hunk 或文件，退出
                    if content_line.startswith('@@') or content_line.startswith('diff --git'):
                        i -= 1
                        break
                    
                    if content_line.startswith('+') and not content_line.startswith('+++'):
                        # 新增行
                        added_lines.append(new_line_num)
                        new_line_num += 1
                    elif content_line.startswith('-') and not content_line.startswith('---'):
                        # 删除行
                        deleted_lines.append(old_line_num)
                        old_line_num += 1
                    elif content_line.startswith(' '):
                        # 上下文行（未修改）
                        new_line_num += 1
                        old_line_num += 1
                    else:
                        # 其他行（可能是空行或注释）
                        pass
                    
                    i += 1
                    
                    # 检查是否已经处理完这个 hunk
                    if len(added_lines) + len(deleted_lines) >= old_count + new_count:
                        break
                
                # 创建 DiffHunk
                hunk = DiffHunk(
                    file_path=current_file,
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    added_lines=added_lines,
                    deleted_lines=deleted_lines,
                    modified_lines=modified_lines
                )
                hunks.append(hunk)
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse hunk header: {line}, error: {e}")
        
        i += 1
    
    return hunks


def build_coverage_index(coverage_blocks: List[CoverageBlock]) -> CoverageIndex:
    """
    构建覆盖率索引（按行号快速查找）
    
    Args:
        coverage_blocks: 覆盖率 block 列表
    
    Returns:
        CoverageIndex: 覆盖率索引
    """
    line_to_blocks: Dict[int, List[CoverageBlock]] = {}
    
    for block in coverage_blocks:
        # 将 block 添加到其覆盖的所有行
        for line_num in range(block.start_line, block.end_line + 1):
            if line_num not in line_to_blocks:
                line_to_blocks[line_num] = []
            line_to_blocks[line_num].append(block)
    
    return CoverageIndex(
        file_path="",  # 文件路径在调用时设置
        line_to_blocks=line_to_blocks
    )


def merge_diff_and_coverage(
    diff_hunks: List[DiffHunk],
    new_coverage_index: CoverageIndex,
    old_coverage_index: Optional[CoverageIndex] = None
) -> List[DiffCoverageFile]:
    """
    融合 Diff 和 Coverage 数据
    
    Args:
        diff_hunks: Git Diff 代码块列表
        new_coverage_index: 新版本的覆盖率索引
        old_coverage_index: 旧版本的覆盖率索引（可选，用于检测覆盖退化/提升）
    
    Returns:
        List[DiffCoverageFile]: 文件级别的融合结果列表
    """
    # 按文件分组
    file_to_hunks: Dict[str, List[DiffHunk]] = {}
    for hunk in diff_hunks:
        if hunk.file_path not in file_to_hunks:
            file_to_hunks[hunk.file_path] = []
        file_to_hunks[hunk.file_path].append(hunk)
    
    # 处理每个文件
    results = []
    for file_path, hunks in file_to_hunks.items():
        lines = []
        
        # 收集所有新增行和修改行
        all_added_lines = set()
        for hunk in hunks:
            all_added_lines.update(hunk.added_lines)
        
        # 对每个新增行，判断其覆盖状态
        for line_num in sorted(all_added_lines):
            new_covered = new_coverage_index.get_line_coverage(line_num)
            hit_count = new_coverage_index.get_line_hit_count(line_num)
            
            # 判断状态
            if new_covered is None:
                # 不可覆盖的行（如注释、空行等），跳过
                continue
            elif new_covered:
                # 新增已覆盖
                status = DiffCoverageStatus.NEW_COVERED
            else:
                # 新增未覆盖
                status = DiffCoverageStatus.NEW_UNCOVERED
            
            lines.append(DiffCoverageLine(
                line_number=line_num,
                status=status,
                hit_count=hit_count,
                is_new=True
            ))
        
        # 如果有旧版本覆盖率索引，检查覆盖退化和提升
        if old_coverage_index:
            # TODO: 实现覆盖退化和提升的检测
            # 需要匹配旧文件和新文件的行号（这比较复杂，暂时不实现）
            pass
        
        # 计算统计信息
        new_uncovered_count = sum(1 for line in lines if line.status == DiffCoverageStatus.NEW_UNCOVERED)
        new_covered_count = sum(1 for line in lines if line.status == DiffCoverageStatus.NEW_COVERED)
        coverage_degraded_count = sum(1 for line in lines if line.status == DiffCoverageStatus.COVERAGE_DEGRADED)
        coverage_improved_count = sum(1 for line in lines if line.status == DiffCoverageStatus.COVERAGE_IMPROVED)
        
        file_result = DiffCoverageFile(
            file_path=file_path,
            lines=lines,
            new_uncovered_count=new_uncovered_count,
            new_covered_count=new_covered_count,
            coverage_degraded_count=coverage_degraded_count,
            coverage_improved_count=coverage_improved_count
        )
        results.append(file_result)
    
    return results


def generate_diff_coverage_summary(file_results: List[DiffCoverageFile]) -> DiffCoverageSummary:
    """
    生成增量覆盖率总结
    
    Args:
        file_results: 文件级别的融合结果列表
    
    Returns:
        DiffCoverageSummary: 增量覆盖率总结
    """
    total_files = len(file_results)
    total_new_lines = 0
    new_uncovered_lines = 0
    new_covered_lines = 0
    coverage_degraded_lines = 0
    coverage_improved_lines = 0
    
    for file_result in file_results:
        total_new_lines += len(file_result.lines)
        new_uncovered_lines += file_result.new_uncovered_count
        new_covered_lines += file_result.new_covered_count
        coverage_degraded_lines += file_result.coverage_degraded_count
        coverage_improved_lines += file_result.coverage_improved_count
    
    # 计算增量覆盖率
    incremental_coverage_rate = 0.0
    total_coverable_lines = new_covered_lines + new_uncovered_lines
    if total_coverable_lines > 0:
        incremental_coverage_rate = (new_covered_lines / total_coverable_lines) * 100
    
    return DiffCoverageSummary(
        total_files=total_files,
        total_new_lines=total_new_lines,
        new_uncovered_lines=new_uncovered_lines,
        new_covered_lines=new_covered_lines,
        coverage_degraded_lines=coverage_degraded_lines,
        coverage_improved_lines=coverage_improved_lines,
        incremental_coverage_rate=incremental_coverage_rate
    )


def generate_monaco_dataset(file_results: List[DiffCoverageFile]) -> Dict:
    """
    生成给 Monaco 编辑器用的最小数据集
    
    格式:
    {
        "files": {
            "file1.go": {
                "lines": {
                    "10": {"status": "new_covered", "hit": 5},
                    "11": {"status": "new_uncovered", "hit": 0},
                    ...
                }
            },
            ...
        }
    }
    
    Args:
        file_results: 文件级别的融合结果列表
    
    Returns:
        Dict: Monaco 数据集
    """
    monaco_data = {"files": {}}
    
    for file_result in file_results:
        lines_data = {}
        for line in file_result.lines:
            lines_data[str(line.line_number)] = {
                "status": line.status.value,
                "hit": line.hit_count
            }
        
        monaco_data["files"][file_result.file_path] = {
            "lines": lines_data
        }
    
    return monaco_data

