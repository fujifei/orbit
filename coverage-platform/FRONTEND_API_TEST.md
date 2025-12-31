# 前端API调用验证指南

## 问题修复总结

### 后端修复 ✅
- 已修复 `manager/repo_manager.py` 中的路径配置问题
- API端点 `/api/coverage/file` 现在可以正确返回文件内容
- API服务器已重启，修复已生效

### 前端增强 ✅
- 已在 `CoverageDetail.jsx` 添加详细的调试日志
- 已在 `DiffCoverageDetail.jsx` 添加详细的调试日志
- 前端会在浏览器控制台输出详细的API调用信息

---

## 如何验证前端是否正确调用API

### 步骤1: 启动前端开发服务器

```bash
cd /Users/jifei.fu/project/qa/orbit/coverage-fe
npm run dev
```

前端服务器通常运行在 `http://localhost:5173` 或 `http://localhost:3000`

### 步骤2: 打开浏览器开发者工具

1. 在浏览器中打开前端应用
2. 按 `F12` 或 `Cmd+Option+I` (Mac) 打开开发者工具
3. 切换到 **Console（控制台）** 标签

### 步骤3: 访问覆盖率详情页

1. 在覆盖率报告列表中点击任意一个报告
2. 在文件树中选择一个文件
3. 观察控制台输出

### 预期的控制台输出

#### ✅ 成功的情况：

```
[API Config] 构建 API URL: { endpoint: '/api/coverage/file', baseUrl: 'http://localhost:8826', finalUrl: 'http://localhost:8826/api/coverage/file', ... }

[CoverageDetail] 正在获取文件内容: {
  repo: 'tuna',
  commit: 'e859c635d19db9fd7250ce668e799f881cc7437a',
  path: 'models/user_repository.go',
  fullRepoUrl: 'https://github.com/fujifei/tuna.git'
}

[CoverageDetail] 文件内容API响应: {
  hasContent: true,
  contentLength: 1688,
  responseData: { content: '...', repo: 'tuna', ... }
}

[CoverageDetail] ✅ 成功设置真实文件内容
```

#### ❌ 失败的情况：

```
[CoverageDetail] 正在获取文件内容: { ... }

[CoverageDetail] ❌ 获取文件内容失败，使用placeholder: Error: ...

[CoverageDetail] 错误详情: {
  message: '...',
  response: { error: '...' },
  status: 404
}
```

### 步骤4: 检查Network（网络）标签

1. 在开发者工具中切换到 **Network（网络）** 标签
2. 刷新页面或重新选择文件
3. 查找 `/api/coverage/file` 的请求
4. 点击该请求查看详情：
   - **Request URL**: 应该是 `http://localhost:8826/api/coverage/file?repo=tuna&commit=xxx&path=xxx`
   - **Status**: 应该是 `200 OK`
   - **Response**: 应该包含 `{ "content": "...", "repo": "tuna", ... }`

---

## 常见问题排查

### 问题1: 控制台显示 "report对象为空"

**原因**: report数据未正确加载

**解决方法**:
```javascript
// 检查控制台是否有报告详情加载失败的错误
// 查看 Network 标签中 /api/v1/coverage/reports/{id} 的响应
```

### 问题2: API返回404或500错误

**原因**: API服务器未运行或路径配置错误

**解决方法**:
```bash
# 检查API服务器状态
curl http://localhost:8826/health

# 重启API服务器
cd /Users/jifei.fu/project/qa/orbit/coverage-platform
./run.sh restart api
```

### 问题3: CORS跨域错误

**原因**: 前端和后端在不同端口，需要CORS支持

**解决方法**: 
- 后端已配置CORS，应该不会有这个问题
- 如果出现，检查 `coverage-api/main.py` 中的 `CORS(app)` 配置

### 问题4: 前端仍显示mock数据（// Line 1, // Line 2...）

**可能原因**:
1. API调用失败（检查控制台错误）
2. report对象为空（检查report数据是否加载）
3. 文件路径不匹配（检查path参数是否正确）

**调试步骤**:
1. 打开浏览器控制台
2. 查看 `[CoverageDetail]` 开头的日志
3. 根据日志信息定位具体问题

---

## 手动测试API

如果前端还有问题，可以先手动测试API：

```bash
# 测试API健康状态
curl http://localhost:8826/health

# 测试获取报告详情（将33替换为实际的报告ID）
curl http://localhost:8826/api/v1/coverage/reports/33

# 测试获取文件内容
curl "http://localhost:8826/api/coverage/file?repo=tuna&commit=e859c635d19db9fd7250ce668e799f881cc7437a&path=models/user_repository.go"
```

---

## 验证清单

- [ ] 后端API服务器正在运行（端口8826）
- [ ] 前端开发服务器正在运行
- [ ] 浏览器控制台没有报错
- [ ] Network标签中看到 `/api/coverage/file` 请求
- [ ] API请求返回200状态码
- [ ] 右侧代码编辑器显示真实代码（不是 // Line 1, // Line 2...）
- [ ] 代码覆盖率高亮显示正常（绿色=已覆盖，红色=未覆盖）

---

## 联系信息

如果按照以上步骤验证后仍有问题，请提供：
1. 浏览器控制台的完整日志
2. Network标签中 `/api/coverage/file` 请求的详细信息
3. 后端API日志（`coverage-platform/logs/api.log`）

## 修改文件列表

本次修复涉及的文件：
- ✅ `coverage-platform/manager/repo_manager.py` - 修复路径配置
- ✅ `coverage-fe/src/components/CoverageDetail.jsx` - 添加调试日志
- ✅ `coverage-fe/src/components/DiffCoverageDetail.jsx` - 添加调试日志

