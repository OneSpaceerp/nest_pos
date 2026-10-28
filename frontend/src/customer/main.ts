import '@shared/app/fonts'
import { createApp, h } from 'vue'
import { dismissSplash, startSurface } from '@shared/app/surface'
import App from './App.vue'

const root = document.getElementById('app')!
startSurface({ app: 'nest_pos_customer', surface: 'customer', root, swUrl: '/nest-pos/customer/sw.js', scope: '/nest-pos/customer/' })
createApp({ render: () => h(App, { root }) }).mount(root)
dismissSplash()
