import '@shared/app/fonts'
import { createApp, h } from 'vue'
import { startSurface } from '@shared/app/surface'
import { setCsrfToken } from '@shared/lib/api'
import App from './App.vue'
import { makeRouter } from './router'

const root = document.getElementById('app')!
startSurface({ app: 'nest_pos', surface: 'staff', root, swUrl: '/nest-pos/sw.js', scope: '/nest-pos/' })
if (import.meta.env.DEV) setCsrfToken(null)

const router = makeRouter('pwa')
createApp({ render: () => h(App, { root }) }).use(router).mount(root)
