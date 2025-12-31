# API 代理调试指南

## 重要说明

**浏览器显示 `http://localhost:3000/api/v1/coverage/reports` 是正常的！**

在浏览器中，相对路径 `/api/v1/coverage/reports` 会被自动解析为完整 URL `http://localhost:3000/api/v1/coverage/reports`。这是浏览器的正常行为。

**关键点：** 虽然浏览器显示的是 3000 端口，但 Vite 开发服务器会自动将 `/api` 开头的请求代理转发到后端服务（端口 8826）。

## 如何验证代理是否正常工作

### 方法 1：查看浏览器控制台

1. 打开浏览器开发者工具（F12）
2. 查看 Console 标签页
3. 你应该能看到类似这样的日志：
   ```
   [API Config] API 配置已初始化: { API_BASE_URL: '(空，使用相对路径)', ... }
   [API Config] 构建 API URL: { finalUrl: '/api/v1/coverage/reports', ... }
   ```

### 方法 2：查看 Vite 服务器日志

1. 查看运行 `npm run dev` 的终端窗口
2. 当你发起 API 请求时，应该能看到类似这样的日志：
   ```
   [Vite Proxy] 代理请求: GET /api/v1/coverage/reports -> http://localhost:8826/api/v1/coverage/reports
   [Vite Proxy] 代理响应: /api/v1/coverage/reports -> 200
   ```

### 方法 3：查看网络请求详情

1. 打开浏览器开发者工具（F12）
2. 切换到 Network 标签页
3. 发起一个 API 请求（例如刷新覆盖率列表）
4. 点击该请求，查看详情：
   - **Request URL**: `http://localhost:3000/api/v1/coverage/reports`（这是正常的）
   - **Status Code**: 应该是 200（如果后端正常）
   - **Response**: 应该能看到后端返回的数据

### 方法 4：直接测试后端服务

在浏览器中直接访问：
```
http://localhost:8826/api/v1/coverage/reports
```

如果这个请求成功，说明后端服务正常运行。

## 常见问题排查

### 问题 1：请求失败，返回 404 或连接错误

**可能原因：**
- 后端服务（端口 8826）没有启动
- Vite 代理配置未生效

**解决方法：**
1. 确认后端服务已启动：`./run.sh status` 或直接访问 `http://localhost:8826/health`
2. 重启前端服务：停止 `npm run dev`，然后重新运行
3. 清除浏览器缓存：Ctrl+Shift+R（Windows/Linux）或 Cmd+Shift+R（Mac）

### 问题 2：看到 CORS 错误

**可能原因：**
- 后端 CORS 配置有问题

**解决方法：**
- 检查后端 `coverage-api/main.go` 中的 CORS 配置

### 问题 3：代理日志没有出现

**可能原因：**
- Vite 配置未生效
- 需要重启开发服务器

**解决方法：**
1. 停止前端服务（Ctrl+C）
2. 删除 `node_modules/.vite` 目录（如果存在）
3. 重新运行 `npm run dev`

## 验证清单

- [ ] 后端服务运行在 8826 端口
- [ ] 前端服务运行在 3000 端口
- [ ] 浏览器控制台显示 API 配置日志
- [ ] Vite 终端显示代理日志
- [ ] 网络请求返回 200 状态码
- [ ] 能够正常获取数据

## 如果问题仍然存在

1. **清除所有缓存：**
   ```bash
   # 清除浏览器缓存（硬刷新）
   # Windows/Linux: Ctrl+Shift+R
   # Mac: Cmd+Shift+R
   
   # 清除 Vite 缓存
   rm -rf node_modules/.vite
   ```

2. **检查环境变量：**
   ```bash
   # 确保没有设置 VITE_API_BASE_URL 环境变量
   # 如果设置了，应该取消设置或设置为空
   unset VITE_API_BASE_URL
   ```

3. **完全重启：**
   ```bash
   # 停止所有服务
   ./run.sh stop
   
   # 重新启动后端
   ./run.sh start
   
   # 重新启动前端
   cd frontend
   npm run dev
   ```

4. **查看详细日志：**
   - 浏览器控制台
   - Vite 终端输出
   - 后端日志：`logs/api.log`

