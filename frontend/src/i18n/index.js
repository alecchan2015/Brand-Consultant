import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.js'
import en from './locales/en.js'
import ja from './locales/ja.js'

export const SUPPORTED_LOCALES = [
  { code: 'zh-CN', label: '简体中文', flag: '🇨🇳' },
  { code: 'en',    label: 'English',   flag: '🇺🇸' },
  { code: 'ja',    label: '日本語',    flag: '🇯🇵' },
]

// Detect initial locale: 1) localStorage override  2) browser lang  3) default zh-CN
function detectLocale() {
  try {
    const saved = localStorage.getItem('ybc_locale')
    if (saved && SUPPORTED_LOCALES.some(l => l.code === saved)) return saved
  } catch {}
  const nav = (navigator.language || navigator.userLanguage || '').toLowerCase()
  if (nav.startsWith('ja')) return 'ja'
  if (nav.startsWith('en')) return 'en'
  return 'zh-CN'
}

const i18n = createI18n({
  legacy: false,                // Composition API mode — use useI18n() in <script setup>
  locale: detectLocale(),
  fallbackLocale: 'en',
  globalInjection: true,        // expose $t() in <template>
  messages: {
    'zh-CN': zhCN,
    'en':    en,
    'ja':    ja,
  },
  warnHtmlMessage: false,
  missingWarn: false,
  fallbackWarn: false,
})

export function setLocale(code) {
  if (!SUPPORTED_LOCALES.some(l => l.code === code)) return
  i18n.global.locale.value = code
  try { localStorage.setItem('ybc_locale', code) } catch {}
  // Update <html lang=""> for accessibility / SEO
  document.documentElement.setAttribute('lang', code)
}

export default i18n
