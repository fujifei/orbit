#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import time
import pika

# CoverageReportMessage 覆盖率报告消息结构
def create_coverage_report_message(repo, branch, commit, ci_provider, ci_pipeline_id, ci_job_id, coverage_format, coverage_raw):
    """创建覆盖率报告消息"""
    # 生成 repo_id: 使用 SHA256 hash
    repo_id = hashlib.sha256(repo.encode('utf-8')).hexdigest()
    
    return {
        'repo': repo,
        'repo_id': repo_id,
        'branch': branch,
        'commit': commit,
        'ci': {
            'provider': ci_provider,
            'pipeline_id': ci_pipeline_id,
            'job_id': ci_job_id
        },
        'coverage': {
            'format': coverage_format,
            'raw': coverage_raw
        },
        'timestamp': int(time.time())
    }


def main():
    # 连接RabbitMQ
    try:
        connection = pika.BlockingConnection(
            pika.URLParameters("amqp://coverage:coverage123@localhost:5672/")
        )
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        return
    
    channel = connection.channel()
    
    # 声明交换机（如果不存在）
    try:
        channel.exchange_declare(
            exchange='coverage_exchange',
            exchange_type='topic',
            durable=True
        )
    except Exception as e:
        print(f"Failed to declare exchange: {e}")
        connection.close()
        return
    
    # 创建示例覆盖率报告
    repo = "github.com/xxx/tuna"
    
    report = create_coverage_report_message(
        repo=repo,
        branch="main",
        commit="a1b2c3d4e5f6",
        ci_provider="gitlab",
        ci_pipeline_id="12345",
        ci_job_id="67890",
        coverage_format="goc",
        coverage_raw="""mode: set
github.com/xxx/tuna/file1.go:10.2,20.3 1
github.com/xxx/tuna/file1.go:30.4,40.5 0
github.com/xxx/tuna/file2.go:5.1,15.2 3
github.com/xxx/tuna/file2.go:20.1,25.3 2"""
    )
    
    # 序列化为JSON
    body = json.dumps(report).encode('utf-8')
    
    # 发布消息（设置持久化）
    try:
        channel.basic_publish(
            exchange='coverage_exchange',
            routing_key='coverage.report',
            body=body,
            properties=pika.BasicProperties(
                content_type='application/json',
                delivery_mode=2,  # 消息持久化
            )
        )
        
        print("Coverage report published successfully!")
        print(f"Repo: {report['repo']}")
        print(f"RepoID: {report['repo_id']}")
        print(f"Branch: {report['branch']}")
        print(f"Commit: {report['commit']}")
    except Exception as e:
        print(f"Failed to publish message: {e}")
    finally:
        channel.close()
        connection.close()


if __name__ == '__main__':
    main()

