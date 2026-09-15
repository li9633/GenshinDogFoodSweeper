import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    // vueDevTools 仅开发环境启用，避免拖慢生产构建
    ...(mode === 'development' ? [vueDevTools()] : []),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: 'auto-imports.d.ts'
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'components.d.ts',
      // 仅扫描 src 目录，跳过 node_modules
      include: [/src\//]
    })
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8765',
        changeOrigin: true
      }
    }
  },
  build: {
    // 现代浏览器无需转译，跳过大量语法降级工作
    target: 'esnext',
    rolldownOptions: {
      output: {
        codeSplitting: true
      }
    }
  }
}))