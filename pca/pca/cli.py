"""
PCA CLI工具
"""
import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PCA] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(description='PCA (Python Coverage Agent) CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # status命令
    status_parser = subparsers.add_parser('status', help='Show PCA status')
    
    # test命令
    test_parser = subparsers.add_parser('test', help='Test PCA agent')
    
    args = parser.parse_args()
    
    if args.command == 'status':
        show_status()
    elif args.command == 'test':
        test_agent()
    else:
        parser.print_help()


def show_status():
    """显示PCA状态"""
    import os
    from pathlib import Path
    
    print("PCA (Python Coverage Agent) Status")
    print("=" * 50)
    
    # 检查环境变量
    enabled = os.getenv('PCA_ENABLED', '1')
    rabbitmq_url = os.getenv('PCA_RABBITMQ_URL', '')
    
    print(f"Enabled: {enabled}")
    print(f"RabbitMQ URL: {rabbitmq_url if rabbitmq_url else '(not configured)'}")
    
    # 检查fingerprint文件
    fingerprint_file = Path.home() / '.pca_fingerprint'
    if fingerprint_file.exists():
        print(f"Fingerprint file: {fingerprint_file} (exists)")
        with open(fingerprint_file, 'r') as f:
            fingerprint = f.read().strip()
            print(f"Last fingerprint: {fingerprint[:16]}...")
    else:
        print(f"Fingerprint file: {fingerprint_file} (not found)")


def test_agent():
    """测试agent"""
    print("Testing PCA Agent...")
    try:
        from pca.agent import CoverageAgent
        
        agent = CoverageAgent()
        print("Agent created successfully")
        
        # 测试覆盖率采集
        agent._flush_coverage()
        print("Coverage flush test completed")
        
        agent.stop()
        print("Agent stopped successfully")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

