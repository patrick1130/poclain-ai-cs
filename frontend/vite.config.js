import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1', // 强制绑定 IPv4 物理环回地址，彻底阻断 IPv6 解析漂移
    port: 5173,
    strictPort: true,  // 端口防漂移锁：若 5173 被幽灵进程占用则直接报错，拒绝自动分配 5174
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})