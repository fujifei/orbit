// API 配置文件
// 统一管理 API 基础 URL
// 
// 配置优先级：
// 1. 环境变量 VITE_API_BASE_URL（最高优先级）
// 2. 开发环境：使用相对路径，通过 Vite 代理转发到后端（端口 8826）
// 3. 生产环境：使用相对路径（假设前后端同域）或环境变量配置的完整 URL

// 获取 API 基础 URL
const getApiBaseUrl = () => {
  // 如果设置了环境变量，优先使用环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    const url = import.meta.env.VITE_API_BASE_URL.trim()
    // 确保环境变量中的 URL 格式正确
    if (url && !url.endsWith('/')) {
      return url
    }
    return url || ''
  }
  
  // 开发环境：使用相对路径，通过 Vite 代理转发到后端（端口 8826）
  // Vite 配置了代理：/api -> http://localhost:8826
  // 所以请求 http://localhost:3000/api/... 会被代理到 http://localhost:8826/api/...
  if (import.meta.env.DEV) {
    return ''
  }
  
  // 生产环境：默认使用相对路径（假设前后端部署在同一域名下）
  // 如果前后端部署在不同域名，必须通过环境变量 VITE_API_BASE_URL 配置
  // 例如：VITE_API_BASE_URL=http://api.example.com
  return ''
}

// API 基础 URL
export const API_BASE_URL = getApiBaseUrl()

// 开发环境下输出配置信息
if (import.meta.env.DEV) {
  console.log('[API Config] API 配置已初始化:', {
    API_BASE_URL: API_BASE_URL || '(空，使用相对路径)',
    isDev: import.meta.env.DEV,
    envVar: import.meta.env.VITE_API_BASE_URL || '(未设置)',
    note: '开发环境：通过 Vite 代理转发到后端 http://localhost:8826'
  })
}

// API 端点
export const API_ENDPOINTS = {
  // 覆盖率报告
  REPORTS: '/api/v1/coverage/reports',
  REPORT_DETAIL: (id) => `/api/v1/coverage/reports/${id}`,
  
  // 覆盖率文件
  FILES: '/api/v1/coverage/files',
  FILE_DETAIL: (id) => `/api/v1/coverage/files/${id}`,
  
  // 增量覆盖率
  DIFF_COVERAGE: (id) => `/api/v1/coverage/reports/${id}/diff`,
  MONACO_DATA: (id) => `/api/v1/coverage/reports/${id}/monaco`,
  
  // 配置管理
  REPO_CONFIG: (repoId) => `/api/v1/coverage/config/${repoId}`,
  UPDATE_BASE_COMMIT: (id) => `/api/v1/coverage/reports/${id}/base-commit`,
  
  // 仓库配置管理（Config页面）
  CONFIGS: '/api/v1/coverage/configs',
  CONFIG_DETAIL: (repoId) => `/api/v1/coverage/configs/${repoId}`,
  GET_REPO_ID: '/api/v1/coverage/configs/repo-id',
}

// 构建完整的 API URL
export const buildApiUrl = (endpoint) => {
  // 如果 endpoint 已经是完整 URL，直接返回
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    console.warn('[API Config] 检测到完整 URL，这可能会绕过代理:', endpoint)
    return endpoint
  }
  
  // 拼接基础 URL 和端点
  const baseUrl = API_BASE_URL.replace(/\/$/, '') // 移除末尾的斜杠
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  const finalUrl = `${baseUrl}${path}`
  
  // 开发环境下输出调试信息
  if (import.meta.env.DEV) {
    console.log('[API Config] 构建 API URL:', {
      endpoint,
      baseUrl: baseUrl || '(空，使用相对路径)',
      finalUrl,
      note: '开发环境：通过 Vite 代理转发到后端 http://localhost:8826'
    })
  }
  
  return finalUrl
}

export default {
  API_BASE_URL,
  API_ENDPOINTS,
  buildApiUrl,
}

