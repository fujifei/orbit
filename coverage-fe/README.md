# Coverage Platform Frontend

覆盖率数据可视化平台前端项目

## 技术栈

### 核心框架
- **React** `^18.2.0` - 用于构建用户界面的 JavaScript 库
- **React DOM** `^18.2.0` - React 的 DOM 渲染器

### 构建工具
- **Vite** `^4.2.0` - 下一代前端构建工具，提供快速的开发体验
- **@vitejs/plugin-react** `^3.1.0` - Vite 的 React 插件

### 路由管理
- **React Router DOM** `^6.8.0` - 用于 React 应用的声明式路由库

### UI 组件库
- **Ant Design** `^6.1.3` - 企业级 UI 设计语言和 React UI 组件库

### HTTP 请求
- **Axios** `^1.3.4` - 基于 Promise 的 HTTP 客户端

### 日期处理
- **Day.js** `^1.11.19` - 轻量级的 JavaScript 日期处理库

### 代码编辑器
- **Monaco Editor** `^0.40.0` - VS Code 使用的代码编辑器
- **@monaco-editor/react** `^4.5.1` - Monaco Editor 的 React 封装

### 开发工具
- **@types/react** `^18.0.28` - React 的 TypeScript 类型定义
- **@types/react-dom** `^18.0.11` - React DOM 的 TypeScript 类型定义

## 项目结构

```
coverage-fe/
├── src/
│   ├── components/          # 组件目录
│   │   ├── ConfigManagement.jsx
│   │   ├── CoverageDetail.jsx
│   │   ├── CoverageList.jsx
│   │   └── DiffCoverageDetail.jsx
│   ├── config/              # 配置文件
│   │   └── api.js
│   ├── utils/               # 工具函数
│   │   └── dateUtils.js
│   ├── App.jsx              # 主应用组件
│   ├── main.jsx             # 应用入口文件
│   └── index.css            # 全局样式
├── index.html               # HTML 模板
├── vite.config.js           # Vite 配置文件
└── package.json             # 项目依赖配置
```

## 开发命令

```bash
# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 开发环境配置

开发服务器运行在 `http://localhost:3000`，并配置了代理将 `/api` 请求转发到后端服务 `http://localhost:8826`。

