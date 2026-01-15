-- ============================================
-- 修复MySQL用户权限脚本
-- ============================================
-- 此脚本用于修复coverage用户从Docker网络连接的权限问题
-- 使用方法：
-- docker exec -i coverage-mysql mysql -uroot -proot123 < fix_mysql_permissions.sql
-- ============================================

-- 创建用户（如果不存在）并授权允许从任何主机连接
CREATE USER IF NOT EXISTS 'coverage'@'%' IDENTIFIED BY 'coverage123';
GRANT ALL PRIVILEGES ON `coverage_db`.* TO 'coverage'@'%';

-- 确保localhost用户也有权限
GRANT ALL PRIVILEGES ON `coverage_db`.* TO 'coverage'@'localhost';

-- 刷新权限
FLUSH PRIVILEGES;

-- 验证权限
SELECT User, Host FROM mysql.user WHERE User = 'coverage';
SHOW GRANTS FOR 'coverage'@'%';
