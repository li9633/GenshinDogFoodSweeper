import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'

import App from './App.vue'
import router from './router'
import './styles/main.scss'

// 初始化主题（从 localStorage 读取，默认暗色）
const savedTheme = localStorage.getItem('genshin-theme') || 'dark'
document.documentElement.setAttribute('data-theme', savedTheme)

const app = createApp(App)

app.component('FontAwesomeIcon', FontAwesomeIcon)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')