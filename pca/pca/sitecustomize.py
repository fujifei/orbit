"""
sitecustomize.py - Python sitecustomize钩子
这个文件会被Python解释器自动加载，用于启动PCA agent
"""
import os
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PCA] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _is_pip_install_context():
    """
    检测是否在pip install过程中
    返回True表示在安装过程中，应该跳过启动agent
    """
    # 检查sys.argv[0]是否包含setup.py或pip
    if len(sys.argv) > 0:
        script_name = sys.argv[0].lower()
        if 'setup.py' in script_name or 'pip' in script_name:
            return True
    
    # 检查环境变量（pip会设置这些变量）
    if os.getenv('PIP_INSTALL') or os.getenv('PIP_REQ_TRACKER'):
        return True
    
    # 检查是否在setup.py的执行上下文中
    # 通过检查调用栈来判断
    import traceback
    stack = traceback.extract_stack()
    for frame in stack:
        filename = frame.filename.lower()
        if 'setup.py' in filename or 'pip' in filename:
            return True
    
    return False

# 检查是否启用PCA
PCA_ENABLED = os.getenv('PCA_ENABLED', '1').lower() in ('1', 'true', 'yes', 'on')

# 检查是否在pip install过程中
if _is_pip_install_context():
    logger.debug("[PCA] Detected pip install context, skipping agent startup")
    PCA_ENABLED = False

if PCA_ENABLED:
    try:
        # 确保pca包在路径中
        # 如果通过.pth文件加载，pca应该已经在sys.path中
        # 但为了保险，我们也尝试从site-packages导入
        try:
            from pca.agent import CoverageAgent
        except ImportError:
            # 如果导入失败，尝试添加路径
            import site
            site_packages = site.getsitepackages()
            if site_packages:
                for sp in site_packages:
                    pca_path = os.path.join(sp, 'pca')
                    if os.path.exists(pca_path):
                        sys.path.insert(0, sp)
                        break
            from pca.agent import CoverageAgent
        
        # 创建并启动agent
        agent = CoverageAgent()
        agent.start()
        
        logger.info("[PCA] Coverage agent started via sitecustomize")
    except Exception as e:
        logger.error(f"[PCA] Failed to start coverage agent: {e}", exc_info=True)
else:
    logger.debug("[PCA] Coverage agent disabled (PCA_ENABLED=0)")

