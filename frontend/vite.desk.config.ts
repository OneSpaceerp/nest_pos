import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const APP = 'nest_pos'

// Loaded by the Desk page (nest_pos_selling/page/nest_pos/nest_pos.js) with frappe.require().
export default defineConfig({
  plugins: [vue({ template: { transformAssetUrls: { includeAbsolute: false } } })],
  resolve: { alias: { '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)) } },
  define: { __NEST_ASSET_ROOT__: JSON.stringify(`/assets/${APP}/frontend/`), 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: `../${APP}/public/desk`,
    emptyOutDir: true,
    target: 'es2020',
    cssCodeSplit: false,
    lib: { entry: 'src/desk/main.ts', name: 'NestPosDesk', formats: ['iife'], fileName: () => 'nest-pos-desk.js', cssFileName: 'nest-pos-desk' },
  },
})
