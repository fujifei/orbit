# 增量覆盖率功能使用说明

## 功能概述

已在现有的 coverage-fe 项目中集成增量覆盖率功能，无需额外的 HTML 文件，直接在 http://localhost:3000 访问。

## 新增功能

### 1. 列表页增强 (/)

在覆盖率报告列表中新增了以下列：

#### 全量覆盖率数据（已有，优化布局）
- 覆盖行
- 总有效行
- 覆盖率

#### 增量系统调测覆盖率数据（新增）
- **新增已覆盖** - 点击可跳转到增量详情页
- **新增总行数** - 点击可跳转到增量详情页
- **覆盖率** - 点击可跳转到增量详情页

#### 其他新增列
- **基准分支** - 显示用于对比的基准分支（默认 master）
- **基准 Commit** - 显示基准 commit hash

#### 操作列优化
- **全量详情** - 查看全量覆盖率详情（原有功能）
- **增量详情** - 查看增量覆盖率详情（新增功能）

### 2. 增量覆盖率详情页 (/diff/:id)

全新的增量覆盖率详情页面，包含：

#### 统计卡片
- **增量覆盖率** - 新增代码的覆盖率百分比
- **新增已覆盖** - 新增且已被测试覆盖的行数
- **新增未覆盖** - 新增但未被测试覆盖的行数
- **覆盖提升** - 原来不覆盖现在覆盖的行数
- **覆盖退化** - 原来覆盖现在不覆盖的行数
- **影响文件** - 有代码变更的文件数

#### 文件详情表格
显示每个文件的详细覆盖率信息：
- 文件路径
- 新增未覆盖行数
- 新增已覆盖行数
- 覆盖退化行数
- 覆盖提升行数

#### 状态说明
- 🟢 **新增已覆盖** - 新增的代码已被测试覆盖
- 🔴 **新增未覆盖** - 新增的代码未被测试覆盖
- 🔵 **覆盖提升** - 原来不覆盖的代码现在覆盖了
- 🟡 **覆盖退化** - 原来覆盖的代码现在不覆盖了

## 技术实现

### 1. API 端点扩展

在 `src/config/api.js` 中新增：

```javascript
// 增量覆盖率
DIFF_COVERAGE: (id) => `/api/v1/coverage/reports/${id}/diff`,
MONACO_DATA: (id) => `/api/v1/coverage/reports/${id}/monaco`,

// 配置管理
REPO_CONFIG: (repoId) => `/api/v1/coverage/config/${repoId}`,
UPDATE_BASE_COMMIT: (id) => `/api/v1/coverage/reports/${id}/base-commit`,
```

### 2. 组件结构

```
src/
├── components/
│   ├── CoverageList.jsx (修改：添加增量覆盖率列)
│   ├── CoverageDetail.jsx (保持不变：全量覆盖率详情)
│   ├── DiffCoverageDetail.jsx (新增：增量覆盖率详情)
│   └── DiffCoverageDetail.css (新增：样式文件)
├── config/
│   └── api.js (修改：添加增量覆盖率 API 端点)
└── App.jsx (修改：添加增量覆盖率路由)
```

### 3. 路由配置

```javascript
<Route path="/" element={<CoverageList />} />
<Route path="/detail/:id" element={<CoverageDetail />} />  // 全量详情
<Route path="/diff/:id" element={<DiffCoverageDetail />} />  // 增量详情（新增）
```

## 使用流程

### 1. 查看列表

访问 http://localhost:3000，即可看到包含增量覆盖率数据的列表：

```
┌───────────────────────────────────────────────────────────────────────┐
│ 仓库 │ 分支 │ Commit │ 基准分支 │ 全量覆盖率 │ 增量覆盖率 │ 操作    │
├───────────────────────────────────────────────────────────────────────┤
│ tuna │ main │ abc123 │ master   │ 800/1000   │ 30/40     │ 详情按钮 │
└───────────────────────────────────────────────────────────────────────┘
```

### 2. 查看增量详情

有三种方式跳转到增量覆盖率详情页：

1. 点击增量覆盖率列中的数字（新增已覆盖、新增总行数、覆盖率）
2. 点击操作列中的"增量详情"按钮
3. 直接访问 URL：`http://localhost:3000/diff/[report_id]`

### 3. 分析增量覆盖率

在详情页面可以：
- 查看整体增量覆盖率统计
- 了解哪些文件有代码变更
- 识别哪些新增代码未被覆盖
- 发现覆盖率退化情况

## 数据流

```
1. 页面加载
   ↓
2. 获取报告列表（/api/v1/coverage/reports）
   ↓
3. 并发获取每个报告的增量覆盖率（/api/v1/coverage/reports/:id/diff）
   ↓
4. 渲染列表（全量 + 增量数据）
   ↓
5. 用户点击增量详情
   ↓
6. 跳转到 /diff/:id 页面
   ↓
7. 获取增量覆盖率详细数据
   ↓
8. 展示统计卡片和文件列表
```

## 性能优化

### 异步加载
- 列表页的增量覆盖率数据采用**异步并发加载**
- 不阻塞页面渲染，提升用户体验
- 使用 `Promise.allSettled` 确保部分失败不影响整体

### 数据缓存
- 增量覆盖率数据存储在组件状态中
- 避免重复请求

## 启动方式

```bash
# 进入前端目录
cd coverage-fe

# 安装依赖（如果尚未安装）
npm install

# 启动开发服务器
npm run dev

# 访问
http://localhost:3000
```

## 后端要求

确保后端 API 服务运行在 `http://localhost:8826`，并实现了以下端点：

- `GET /api/v1/coverage/reports` - 报告列表
- `GET /api/v1/coverage/reports/:id` - 报告详情
- `GET /api/v1/coverage/reports/:id/diff` - 增量覆盖率
- `GET /api/v1/coverage/reports/:id/monaco` - Monaco 数据集
- `GET /api/v1/coverage/config/:repo_id` - 配置查询
- `POST /api/v1/coverage/config/:repo_id` - 配置设置

## CI/CD 集成

### 示例：在 CI 中使用增量覆盖率

```bash
# 上报覆盖率后获取 report_id
REPORT_ID=123

# 获取增量覆盖率
RATE=$(curl -s "http://localhost:8826/api/v1/coverage/reports/${REPORT_ID}/diff" \
  | jq '.summary.incremental_coverage_rate')

# 检查是否达标
if (( $(echo "$RATE < 80" | bc -l) )); then
  echo "❌ 增量覆盖率不足: ${RATE}%"
  exit 1
else
  echo "✅ 增量覆盖率达标: ${RATE}%"
fi
```

## 注意事项

1. **首次加载可能较慢** - 增量覆盖率数据需要计算 Git Diff，首次请求可能需要几秒
2. **需要 Git 仓库** - 后端必须能访问到 Git 仓库才能计算 Diff
3. **基准分支配置** - 不同仓库可能需要配置不同的基准分支（master/main/release）
4. **浏览器兼容性** - 建议使用现代浏览器（Chrome、Firefox、Edge）

## 故障排查

### 问题1：增量覆盖率数据显示为 "-"

**原因：**
- 后端计算失败
- Git Diff 为空（没有变更）
- 基准分支配置错误

**解决：**
1. 打开浏览器开发者工具，查看 Network 标签
2. 检查 `/api/v1/coverage/reports/:id/diff` 请求是否成功
3. 查看后端日志：`tail -f coverage-platform/logs/api.log`

### 问题2：点击增量详情无响应

**原因：**
- 路由配置错误
- 报告 ID 无效

**解决：**
1. 确认 `App.jsx` 中已添加 `/diff/:id` 路由
2. 检查浏览器控制台是否有错误
3. 确认报告 ID 存在

### 问题3：页面加载很慢

**原因：**
- 报告数量太多，并发请求增量覆盖率导致

**解决：**
1. 使用分页，减少单页报告数量
2. 考虑后端预计算增量覆盖率
3. 添加缓存机制

## 后续优化建议

1. **增量覆盖率预计算** - 在 Consumer 中预计算，加快前端加载速度
2. **Monaco 集成** - 在代码编辑器中直观显示增量覆盖率
3. **趋势图表** - 展示增量覆盖率的历史趋势
4. **导出功能** - 支持导出增量覆盖率报告
5. **告警功能** - 增量覆盖率低于阈值时发送通知

## 相关文档

- [后端增量覆盖率 API 文档](../coverage-platform/DIFF_COVERAGE_README.md)
- [增量覆盖率实现总结](../coverage-platform/IMPLEMENTATION_SUMMARY.md)
- [快速开始指南](../coverage-platform/QUICKSTART_DIFF_COVERAGE.md)

## 技术支持

如有问题，请：
1. 查看浏览器控制台错误
2. 查看后端日志：`coverage-platform/logs/api.log`
3. 查看详细文档
4. 联系技术支持

---

**功能已完成！** 🎉  
现在可以在 http://localhost:3000 查看完整的全量和增量覆盖率功能。

