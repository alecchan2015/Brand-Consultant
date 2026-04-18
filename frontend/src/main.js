import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElIcons from '@element-plus/icons-vue'

// Element Plus language packs — sync to the active i18n locale below
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en   from 'element-plus/es/locale/lang/en'
import ja   from 'element-plus/es/locale/lang/ja'

import App from './App.vue'
import router from './router'
import i18n from './i18n'

const elLocaleMap = { 'zh-CN': zhCn, 'en': en, 'ja': ja }

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(i18n)
app.use(ElementPlus, {
  size: 'default',
  zIndex: 3000,
  locale: elLocaleMap[i18n.global.locale.value] || zhCn,
})

// Update <html lang=""> for SEO + accessibility
document.documentElement.setAttribute('lang', i18n.global.locale.value)

Object.keys(ElIcons).forEach(key => {
  app.component(key, ElIcons[key])
})

app.mount('#app')
