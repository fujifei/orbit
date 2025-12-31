#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import sys
import os
from typing import Dict, Optional

# 添加父目录到路径，以便导入共享模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pika

from models import init_db
from manager.manager import CoverageReportMessage, process_coverage_report

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 常量
MAX_RETRY_COUNT = 10  # 最大重试次数
RETRY_HEADER_KEY = 'x-retry-count'  # 重试次数header键

# RabbitMQ配置
RABBITMQ_URL = "amqp://coverage:coverage123@localhost:5672/"


def get_retry_count(headers: Optional[Dict]) -> int:
    """从消息headers中获取重试次数"""
    if not headers:
        return 0
    
    if RETRY_HEADER_KEY in headers:
        retry_count_val = headers[RETRY_HEADER_KEY]
        if isinstance(retry_count_val, int):
            return retry_count_val
        elif isinstance(retry_count_val, str):
            try:
                return int(retry_count_val)
            except ValueError:
                pass
    
    return 0


def connect_rabbitmq() -> pika.BlockingConnection:
    """连接RabbitMQ"""
    try:
        parameters = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(parameters)
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise


def setup_queue(channel: pika.channel.Channel) -> None:
    """设置队列"""
    # 声明交换机
    channel.exchange_declare(
        exchange='coverage_exchange',
        exchange_type='topic',
        durable=True
    )
    
    # 声明队列
    channel.queue_declare(
        queue='coverage_queue',
        durable=True
    )
    
    # 绑定队列到交换机
    channel.queue_bind(
        exchange='coverage_exchange',
        queue='coverage_queue',
        routing_key='coverage.report'
    )


def main():
    logger.info("Starting Coverage Consumer Service...")
    
    # 初始化数据库
    init_db()
    
    # 连接RabbitMQ
    connection = connect_rabbitmq()
    channel = connection.channel()
    
    try:
        # 设置队列
        setup_queue(channel)
        
        # 设置QoS，确保公平分发
        channel.basic_qos(prefetch_count=1)
        
        logger.info("Waiting for coverage reports...")
        
        def callback(ch, method, properties, body):
            """消息处理回调"""
            message_id = properties.message_id or 'N/A'
            logger.info(
                f"[消息接收] 收到覆盖率报告消息, 消息大小: {len(body)} bytes, 消息ID: {message_id}"
            )
            
            # 获取当前重试次数
            headers = properties.headers or {}
            retry_count = get_retry_count(headers)
            logger.info(f"[消息接收] 当前重试次数: {retry_count}/{MAX_RETRY_COUNT}")
            
            report_msg = None
            try:
                # 解析消息
                data = json.loads(body.decode('utf-8'))
                report_msg = CoverageReportMessage(data)
                
                # 打印接收到的消息详细信息
                logger.info(
                    f"[消息接收] 覆盖率报告详情 - repo={report_msg.repo}, "
                    f"repo_id={report_msg.repo_id}, branch={report_msg.branch}, "
                    f"commit={report_msg.commit}, format={report_msg.coverage.get('format')}, "
                    f"timestamp={report_msg.timestamp}"
                )
                
                # 验证必需字段
                if not report_msg.repo_id:
                    logger.warning("[消息消费失败] RepoID为空, 无法处理消息")
                    logger.warning(f"[消息消费失败] 重试次数: {retry_count}/{MAX_RETRY_COUNT}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                
                # 处理报告
                process_coverage_report(report_msg)
                
                # 消息消费成功
                logger.info("[消息消费成功] 覆盖率报告处理完成")
                logger.info(
                    f"[消息消费成功] 仓库信息: repo={report_msg.repo}, "
                    f"repo_id={report_msg.repo_id}, branch={report_msg.branch}, "
                    f"commit={report_msg.commit}"
                )
                logger.info(f"[消息消费成功] 重试次数: {retry_count}/{MAX_RETRY_COUNT}")
                
                # 确认消息
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("[消息消费成功] 消息已确认")
                
            except json.JSONDecodeError as e:
                # JSON解析失败
                logger.error(f"[消息消费失败] JSON解析失败, 错误: {e}")
                body_preview = body[:500].decode('utf-8', errors='ignore')
                logger.error(f"[消息消费失败] 消息内容(前500字符): {body_preview}")
                logger.error(f"[消息消费失败] 重试次数: {retry_count}/{MAX_RETRY_COUNT}")
                # JSON解析失败通常不应该重试，直接拒绝
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                
            except Exception as e:
                # 处理失败
                logger.error("[消息消费失败] 处理覆盖率报告失败")
                if report_msg:
                    logger.error(
                        f"[消息消费失败] 仓库信息: repo={report_msg.repo}, "
                        f"repo_id={report_msg.repo_id}, branch={report_msg.branch}, "
                        f"commit={report_msg.commit}"
                    )
                else:
                    logger.error("[消息消费失败] 仓库信息: N/A (消息解析失败)")
                logger.error(f"[消息消费失败] 错误详情: {e}")
                logger.error(f"[消息消费失败] 当前重试次数: {retry_count}/{MAX_RETRY_COUNT}")
                
                # 检查重试次数
                if retry_count >= MAX_RETRY_COUNT:
                    logger.error(
                        f"[消息消费失败] 已达到最大重试次数({MAX_RETRY_COUNT}次), "
                        "不再重试, 消息将被丢弃"
                    )
                    if report_msg:
                        repo_info = f"repo={report_msg.repo}, repo_id={report_msg.repo_id}"
                    else:
                        repo_info = "N/A"
                    logger.error(f"[消息消费失败] 最终失败信息: {repo_info}, error={e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                
                # 增加重试次数并重新入队
                new_retry_count = retry_count + 1
                logger.info(
                    f"[消息消费失败] 将重试处理, 下次重试次数: {new_retry_count}/{MAX_RETRY_COUNT}"
                )
                
                # 准备新的headers
                new_headers = headers.copy() if headers else {}
                new_headers[RETRY_HEADER_KEY] = new_retry_count
                
                # 重新发布消息
                try:
                    ch.basic_publish(
                        exchange='coverage_exchange',
                        routing_key='coverage.report',
                        body=body,
                        properties=pika.BasicProperties(
                            content_type=properties.content_type,
                            delivery_mode=properties.delivery_mode,
                            message_id=properties.message_id,
                            headers=new_headers
                        )
                    )
                    # 确认原消息（因为我们已经重新发布了）
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as pub_err:
                    logger.error(f"[消息消费失败] 重新发布消息失败: {pub_err}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        # 消费消息
        channel.basic_consume(
            queue='coverage_queue',
            on_message_callback=callback,
            auto_ack=False
        )
        
        # 开始消费
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
        channel.stop_consuming()
    except Exception as e:
        logger.error(f"Error in consumer: {e}")
        raise
    finally:
        channel.close()
        connection.close()


if __name__ == '__main__':
    main()
