import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    // 开发环境代理配置：将 /api 请求代理到后端服务（端口 8826）
    // 重要：所有以 /api 开头的请求都会被转发到 http://localhost:8826
    proxy: {
      '/api': {
        target: 'http://localhost:8826',
        changeOrigin: true,
        secure: false,
        // 不重写路径，直接转发
        // 例如：/api/v1/coverage/reports -> http://localhost:8826/api/v1/coverage/reports
      }
    }
  },
  // 构建配置
  build: {
    outDir: 'dist',
    sourcemap: false,
  }
})

