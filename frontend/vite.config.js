import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ['echarts'],
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
  server: {
    port: 8021,
    proxy: {
      '/api': 'http://localhost:8020'
    }
  }
})
