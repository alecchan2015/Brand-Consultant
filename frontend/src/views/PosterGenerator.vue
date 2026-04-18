<template>
  <div class="poster-page">
    <!-- Top -->
    <button class="back-btn" @click="$router.push('/dashboard')">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M10 4L6 8l4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>{{ $t('common.backToDashboard') }}</span>
    </button>

    <div class="page-hero">
      <div class="hero-badge">
        <span class="dot"></span>
        <span>{{ $t('poster.badge') }}</span>
      </div>
      <h1>{{ $t('poster.title') }}</h1>
      <p>{{ $t('poster.subtitle') }}</p>
    </div>

    <!-- Form (when no active generation) -->
    <div v-if="!generationId || generationError" class="form-card">
      <!-- Brand (only required field) -->
      <div class="field">
        <label>{{ $t('poster.brand') }} <span class="req">*</span></label>
        <input v-model="form.brandName" class="field-input" :placeholder="$t('poster.brandPlaceholder')"
          maxlength="40" />
      </div>

      <!-- Event keyword — categorized picker with search (optional) -->
      <div class="field">
        <label>{{ $t('poster.event') }} <span class="opt">{{ $t('poster.eventHintOpt') }}</span></label>
        <input v-model="form.eventKeyword" class="field-input"
          :placeholder="$t('poster.eventPlaceholder')" maxlength="20" />

        <div class="kw-browser">
          <!-- Category tabs -->
          <div class="kw-tabs">
            <button v-for="cat in keywordCategories" :key="cat.key"
              class="kw-tab" :class="{ active: activeCategory === cat.key }"
              @click="activeCategory = cat.key">
              <span class="kw-tab-icon">{{ cat.icon }}</span>
              <span class="kw-tab-label">{{ cat.label }}</span>
              <span class="kw-tab-count">{{ cat.items.length }}</span>
            </button>
          </div>

          <!-- Search bar for the current category -->
          <div class="kw-search-row">
            <input v-model="kwSearch" class="kw-search"
              :placeholder="$t('poster.kwBrowser.searchPlaceholder')" />
            <span class="kw-hint">{{ $t('poster.kwBrowser.shown', { n: filteredKeywords.length }) }}</span>
          </div>

          <!-- Keyword grid -->
          <div class="kw-grid">
            <button v-for="kw in filteredKeywords" :key="kw"
              class="kw-item" :class="{ active: form.eventKeyword === kw }"
              @click="form.eventKeyword = kw">{{ kw }}</button>
            <div v-if="!filteredKeywords.length" class="kw-empty">
              {{ $t('poster.kwBrowser.empty') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Slogan + subline row (both optional) -->
      <div class="row-2">
        <div class="field">
          <label>{{ $t('poster.slogan') }} <span class="opt">{{ $t('poster.sloganHint') }}</span></label>
          <input v-model="form.headline" class="field-input"
            :placeholder="$t('poster.sloganPlaceholder')" maxlength="30" />
        </div>
        <div class="field">
          <label>{{ $t('poster.subline') }} <span class="opt">{{ $t('poster.sublineHint') }}</span></label>
          <input v-model="form.subline" class="field-input"
            :placeholder="$t('poster.sublinePlaceholder')" maxlength="60" />
        </div>
      </div>

      <!-- Industry + size + style row -->
      <div class="row-3">
        <div class="field">
          <label>{{ $t('poster.industry') }}</label>
          <select v-model="form.industry" class="field-input">
            <option value="">{{ $t('poster.industryAuto') }}</option>
            <option value="家居家具">{{ $t('logo.industries.furniture') }}</option>
            <option value="美妆护肤">{{ $t('logo.industries.beauty') }}</option>
            <option value="科技智能">{{ $t('logo.industries.tech') }}</option>
            <option value="食品饮料">{{ $t('logo.industries.food') }}</option>
            <option value="服装时尚">{{ $t('logo.industries.fashion') }}</option>
            <option value="教育培训">{{ $t('logo.industries.education') }}</option>
            <option value="医疗健康">{{ $t('logo.industries.health') }}</option>
          </select>
        </div>
        <div class="field">
          <label>{{ $t('poster.size') }}</label>
          <select v-model="form.size" class="field-input">
            <option value="portrait">{{ $t('poster.sizes.portrait') }}</option>
            <option value="story">{{ $t('poster.sizes.story') }}</option>
            <option value="square">{{ $t('poster.sizes.square') }}</option>
            <option value="landscape">{{ $t('poster.sizes.landscape') }}</option>
            <option value="a3">{{ $t('poster.sizes.a3') }}</option>
          </select>
        </div>
        <div class="field">
          <label>{{ $t('poster.primaryColor') }}</label>
          <div class="color-input-row">
            <input type="color" v-model="form.primaryColor" class="color-swatch" />
            <input v-model="form.primaryColor" class="field-input color-hex" placeholder="#6366f1" maxlength="7" />
          </div>
        </div>
      </div>

      <!-- Product image upload (optional) -->
      <div class="field">
        <label>{{ $t('poster.productImage') }}</label>
        <div class="product-uploader" :class="{ 'has-image': productPreview, dragging }"
          @click="!productPreview && $refs.fileInput.click()"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDropFile">
          <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp"
            style="display:none" @change="onFileChange" />

          <!-- Preview -->
          <div v-if="productPreview" class="product-preview">
            <img :src="productPreview" alt="product" />
            <div class="product-overlay">
              <span v-if="productUploading" class="product-hint">{{ $t('poster.productUploading') }}</span>
              <span v-else class="product-hint ok">✓ {{ $t('poster.productUploaded') }}</span>
              <button class="product-remove" @click.stop="removeProduct">
                {{ $t('poster.productRemove') }}
              </button>
            </div>
          </div>

          <!-- Empty drop zone -->
          <div v-else class="product-drop">
            <div class="product-drop-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.5"/>
                <circle cx="9" cy="9" r="2" stroke="currentColor" stroke-width="1.5"/>
                <path d="M3 16l5-5 4 4 3-3 6 6" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="product-drop-label">{{ $t('poster.productDrop') }}</div>
            <div class="product-drop-hint">{{ $t('poster.productAccept') }}</div>
          </div>
        </div>
        <div class="product-hint-below">{{ $t('poster.productImageHint') }}</div>
      </div>

      <!-- Style picker -->
      <div class="field">
        <label>{{ $t('poster.style') }}</label>
        <div class="style-grid">
          <div
            v-for="s in styles" :key="s.value"
            class="style-card"
            :class="{ selected: form.style === s.value }"
            @click="form.style = s.value"
          >
            <span class="style-icon">{{ s.icon }}</span>
            <span class="style-label">{{ s.label }}</span>
          </div>
        </div>
      </div>

      <!-- Credit info -->
      <div class="credit-row">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5"/>
          <path d="M8 4v4l2.5 1.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span>{{ $t('poster.creditInfo', { cost: creditCost, balance: userCredits }) }}</span>
        <span v-if="userCredits < creditCost" class="insufficient">{{ $t('poster.insufficient') }}</span>
      </div>

      <button class="generate-btn" :disabled="!canGenerate || generating" @click="handleGenerate">
        <span v-if="generating" class="spinner"></span>
        <svg v-else width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M9 1L11 6L16 7L12 11L13 16L9 13.5L5 16L6 11L2 7L7 6L9 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        </svg>
        <span>{{ generating ? $t('poster.submitting') : $t('poster.submit') }}</span>
      </button>
    </div>

    <!-- Progress -->
    <div v-if="generationId && !generationDone && !generationError" class="progress-card">
      <div class="progress-head">
        <div class="pulse"></div>
        <span>{{ $t('poster.progress.title') }}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progress.percent + '%' }"></div>
      </div>
      <div class="progress-steps">
        <div v-for="(step, idx) in progressSteps" :key="idx"
          class="progress-step"
          :class="{ active: progress.percent >= step.at && progress.percent < (progressSteps[idx + 1]?.at || 101),
                    done:   progress.percent >= (progressSteps[idx + 1]?.at || 101) }">
          <span class="step-dot" />
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="generationError" class="error-banner">
      <span>⚠️</span><span>{{ generationError }}</span>
      <button class="clear-btn" @click="generationError = ''">✕</button>
    </div>

    <!-- Result -->
    <div v-if="generationDone && variants.length" class="result-card">
      <div class="result-head">
        <h3>{{ $t('poster.result.title') }}</h3>
        <button class="ghost-btn" @click="handleReset">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M13 3v4h-4M3 13v-4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4.2 6a5 5 0 018-1.5L13 7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          {{ $t('poster.result.reset') }}
        </button>
      </div>

      <div class="variant-wrapper">
        <div v-for="(v, idx) in variants" :key="idx" class="variant-item"
          :class="{ selected: selectedVariant === idx }"
          @click="selectedVariant = idx">
          <div class="variant-preview">
            <img :src="posterImgUrl(v)" :alt="$t('poster.result.variant', { n: idx + 1 })" />
          </div>
          <div class="variant-label">{{ $t('poster.result.variant', { n: idx + 1 }) }}</div>
        </div>
      </div>

      <div class="download-row">
        <button class="download-btn primary" @click="handleDownload">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2v9M4 7l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M3 14h10" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
          {{ $t('poster.result.dlBtn') }}
        </button>
      </div>
    </div>

    <!-- History -->
    <div class="history-card">
      <div class="history-head">
        <h3>📋 {{ $t('poster.history.title') }}</h3>
        <button class="ghost-btn small" @click="loadHistory">{{ $t('poster.history.refresh') }}</button>
      </div>
      <div v-if="!history.length && !historyLoading" class="history-empty">
        {{ $t('poster.history.empty') }}
      </div>
      <div v-else class="history-list">
        <div v-for="item in history" :key="item.id" class="history-item"
          @click="viewHistory(item)">
          <div class="history-preview">
            <img v-if="item.variants?.[0]?.png_url" :src="historyImgUrl(item)" :alt="item.brand_name" />
            <div v-else class="history-placeholder">
              {{ item.status === 'processing' ? '⏳' : '❌' }}
            </div>
          </div>
          <div class="history-info">
            <div class="history-title">{{ item.brand_name }} · {{ item.event_keyword }}</div>
            <div class="history-meta">
              <span class="status-chip" :class="`s-${item.status}`">
                {{ item.status === 'done' ? $t('poster.history.statusDone') : (item.status === 'failed' ? $t('poster.history.statusFailed') : $t('poster.history.statusProcessing')) }}
              </span>
              <span>{{ styleLabel(item.style) }}</span>
              <span class="time">{{ formatTime(item.created_at) }}</span>
            </div>
          </div>
          <button v-if="item.status === 'done'" class="history-dl" @click.stop="downloadHistory(item)">
            {{ $t('poster.history.download') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../store'
import { posterAPI } from '../api'

// ── i18n ─────────────────────────────────────────────
const { t } = useI18n()

const store = useUserStore()
const userCredits = computed(() => store.user?.credits ?? 0)

const form = reactive({
  brandName: '',
  eventKeyword: '',
  headline: '',
  subline: '',
  industry: '',
  size: 'portrait',
  style: 'natural',
  primaryColor: '',
  productImageUrl: '',   // set after successful upload
})

// ── Product image upload state ───────────────────────────────────
const fileInput = ref(null)
const productPreview = ref('')
const productUploading = ref(false)
const dragging = ref(false)

function _validateFile(f) {
  const ok = ['image/png', 'image/jpeg', 'image/webp'].includes(f.type)
  if (!ok) { ElMessage.error(t('poster.productInvalidType')); return false }
  if (f.size > 10 * 1024 * 1024) { ElMessage.error(t('poster.productTooLarge')); return false }
  return true
}

async function _doUpload(file) {
  if (!_validateFile(file)) return
  // Local preview first (immediate UX)
  const reader = new FileReader()
  reader.onload = (e) => { productPreview.value = e.target.result }
  reader.readAsDataURL(file)

  productUploading.value = true
  try {
    const res = await posterAPI.uploadProduct(file)
    form.productImageUrl = res.url
  } catch (e) {
    ElMessage.error(e.message || 'upload failed')
    productPreview.value = ''
    form.productImageUrl = ''
  } finally {
    productUploading.value = false
  }
}

function onFileChange(e) {
  const f = e.target.files?.[0]
  if (f) _doUpload(f)
  if (fileInput.value) fileInput.value.value = ''  // allow re-selecting same file
}
function onDropFile(e) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) _doUpload(f)
}
function removeProduct() {
  productPreview.value = ''
  form.productImageUrl = ''
}

const styles = computed(() => [
  { value: 'natural',  icon: '🌿', label: t('poster.styles.natural') },
  { value: 'luxury',   icon: '💎', label: t('poster.styles.luxury') },
  { value: 'modern',   icon: '🔲', label: t('poster.styles.modern') },
  { value: 'playful',  icon: '🎈', label: t('poster.styles.playful') },
  { value: 'heritage', icon: '🏮', label: t('poster.styles.heritage') },
])

const keywordCategories = computed(() => [
  {
    key: 'seasons', icon: '🌿', label: t('poster.kwBrowser.categories.seasons'),
    items: [
      // 春
      '立春', '雨水', '惊蛰', '春分', '清明', '谷雨',
      // 夏
      '立夏', '小满', '芒种', '夏至', '小暑', '大暑',
      // 秋
      '立秋', '处暑', '白露', '秋分', '寒露', '霜降',
      // 冬
      '立冬', '小雪', '大雪', '冬至', '小寒', '大寒',
    ],
  },
  {
    key: 'festivals', icon: '🎉', label: t('poster.kwBrowser.categories.festivals'),
    items: [
      '春节', '除夕', '元宵', '龙抬头', '上巳', '寒食', '清明祭',
      '端午', '七夕', '中元', '中秋', '重阳', '下元', '腊八',
      '小年', '元旦', '开工大吉', '迎春纳福',
    ],
  },
  {
    key: 'modern', icon: '💝', label: t('poster.kwBrowser.categories.modern'),
    items: [
      '元旦', '情人节', '妇女节', '女神节', '植树节', '愚人节',
      '劳动节', '青年节', '母亲节', '儿童节', '父亲节', '建军节',
      '教师节', '中秋节', '国庆节', '万圣节', '感恩节', '圣诞节',
      '平安夜', '跨年夜', '白色情人节', '520 告白日',
    ],
  },
  {
    key: 'marketing', icon: '🛍️', label: t('poster.kwBrowser.categories.marketing'),
    items: [
      // 电商大促
      '年货节', '女王节', '开学季', '国货节', '618 大促', '618 狂欢',
      '818 发烧节', '99 划算节', '双 11', '双 12', '99 超级粉丝节',
      '年终盛典', '双旦季', '元宵大促',
      // 活动类型
      '新品发布', '新品首发', '限时特惠', '清仓大促', '抢购专场',
      '预售开启', '拼团狂欢', '秒杀专场', '闪购特卖', '满减活动',
      '会员日', 'VIP 专享', '品牌日', '超级品牌日',
      // 店铺里程碑
      '开业盛典', '新店开业', '周年庆典', '十年风华',
      '门店焕新', '旗舰店开业', '入驻庆典',
    ],
  },
  {
    key: 'furniture', icon: '🛋️', label: t('poster.kwBrowser.categories.furniture'),
    items: [
      // 产品类
      '沙发焕新', '床垫专场', '茶几臻选', '餐桌大促',
      '衣柜定制', '书柜专场', '全屋定制', '整装设计',
      '智能家具', '红木经典', '实木臻品', '北欧简约',
      '轻奢系列', '新中式美学', '美式风范', '日式禅意',
      // 建材类
      '春季装修节', '夏季装修季', '秋冬装修狂欢', '地板专场',
      '瓷砖专场', '卫浴特惠', '涂料焕新', '灯饰美学',
      '门窗升级', '五金精选', '窗帘布艺', '墙纸墙布',
      '橱柜定制', '吊顶专场', '楼梯定制', '石材臻选',
      // 场景主题
      '新居入住', '乔迁之喜', '开工吉日', '竣工仪式',
      '软装搭配', '空间改造', '旧屋翻新', '精装美学',
      '极简生活', '慢生活', '高定家居', '设计师臻选',
      '一站式购齐', '原木家居', '匠心工艺',
    ],
  },
  {
    key: 'lifestyle', icon: '🌅', label: t('poster.kwBrowser.categories.lifestyle'),
    items: [
      '质造生活', '美好家居', '匠心如初', '家的温度',
      '归心之所', '舒适空间', '理想居所', '烟火人间',
      '闲适午后', '晨光初现', '黄昏薄暮', '静谧时光',
      '周末放空', '家庭时光', '亲子乐园', '独处美学',
      '茶香书韵', '阅读时光', '慢煮光阴', '咖啡时光',
      '治愈系', '温暖色调', '诗意栖居', '返璞归真',
    ],
  },
  {
    key: 'scenes', icon: '🏠', label: t('poster.kwBrowser.categories.scenes'),
    items: [
      '客厅美学', '卧室温馨', '书房雅韵', '餐厨烟火',
      '儿童房', '玄关第一印象', '阳台花园', '浴室焕新',
      '书桌一隅', '茶室禅意', '衣帽间', '储藏间',
      '小户型优雅', '大平层豪宅', '别墅臻品', '民宿美学',
      '办公空间', '会客厅', '咖啡厅', '精品酒店',
    ],
  },
  {
    key: 'vibe', icon: '✨', label: t('poster.kwBrowser.categories.vibe'),
    items: [
      '新年伊始', '春意盎然', '夏日清凉', '金秋收获', '冬日温暖',
      '年末盘点', '跨年时刻', '感恩回馈', '开工纳福',
      '团圆喜庆', '浪漫氛围', '文艺清新', '治愈系',
      '国潮东方', '复古港风', '赛博未来', '极简禅意',
      '暖阳午后', '月色阑珊', '晨雾朦胧', '细雨如丝',
    ],
  },
])

// Active category + search state
const activeCategory = ref('seasons')
const kwSearch = ref('')
const filteredKeywords = computed(() => {
  const cat = keywordCategories.value.find(c => c.key === activeCategory.value)
  if (!cat) return []
  const q = kwSearch.value.trim().toLowerCase()
  if (!q) return cat.items
  return cat.items.filter(k => k.toLowerCase().includes(q))
})

const creditCost = computed(() => 5)
const canGenerate = computed(() =>
  form.brandName.trim() && userCredits.value >= creditCost.value
)

// Generation state
const generating = ref(false)
const generationId = ref('')
const generationDone = ref(false)
const generationError = ref('')
const variants = ref([])
const selectedVariant = ref(0)
const progress = reactive({ percent: 0, label: '' })
let eventSource = null

const progressSteps = computed(() => [
  { label: t('poster.progress.steps.prepare'), at: 5 },
  { label: t('poster.progress.steps.bg'),      at: 30 },
  { label: t('poster.progress.steps.compose'), at: 70 },
  { label: t('poster.progress.steps.done'),    at: 100 },
])

async function handleGenerate() {
  if (!canGenerate.value) return
  generating.value = true
  generationDone.value = false
  generationError.value = ''
  variants.value = []
  progress.percent = 0

  try {
    const res = await posterAPI.generate({
      brand_name:    form.brandName,
      event_keyword: form.eventKeyword,
      headline:      form.headline || null,
      subline:       form.subline || null,
      industry:      form.industry || null,
      size:          form.size,
      style:         form.style,
      primary_color: form.primaryColor || null,
      product_image_url: form.productImageUrl || null,
    })
    generationId.value = res.generation_id
    store.fetchMe().catch(() => {})
    startProgressPolling(res.generation_id)
  } catch (e) {
    generationError.value = e.message || t('poster.errConnection')
    ElMessage.error(generationError.value)
  } finally {
    generating.value = false
  }
}

function startProgressPolling(id) {
  closeEventSource()
  const token = localStorage.getItem('token')
  eventSource = new EventSource(posterAPI.progressUrl(id, token))

  eventSource.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        progress.percent = data.percent ?? progress.percent
        progress.label = data.label ?? ''
      } else if (data.type === 'done') {
        progress.percent = 100
        generationDone.value = true
        variants.value = data.variants || []
        selectedVariant.value = 0
        closeEventSource()
        loadHistory()
        ElMessage.success(t('poster.successGen'))
      } else if (data.type === 'error') {
        generationError.value = data.message || t('poster.errConnection')
        closeEventSource()
        ElMessage.error(generationError.value)
      }
    } catch { /* skip */ }
  }
  eventSource.onerror = () => {
    closeEventSource()
    if (!generationDone.value && !generationError.value) {
      generationError.value = t('poster.errConnection')
    }
  }
}

function closeEventSource() {
  if (eventSource) { eventSource.close(); eventSource = null }
}

function _appendToken(url) {
  if (!url) return ''
  // External URLs (TOS/ARK, etc.) — browser can load directly, don't touch
  if (/^https?:\/\//i.test(url)) return url
  // Local /api/... URLs need our JWT so <img> can authenticate
  const token = localStorage.getItem('token') || ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}token=${encodeURIComponent(token)}`
}

function posterImgUrl(v) {
  return _appendToken(v?.png_url || '')
}

function historyImgUrl(item) {
  return _appendToken(item.variants?.[0]?.png_url || '')
}

function handleDownload() {
  if (!generationId.value) return
  const a = document.createElement('a')
  a.href = posterAPI.downloadUrl(generationId.value)
  a.download = `${form.brandName}_${form.eventKeyword}_poster.png`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  ElMessage.success(t('poster.downloadStarted'))
}

function handleReset() {
  generationId.value = ''
  generationDone.value = false
  generationError.value = ''
  variants.value = []
  progress.percent = 0
  selectedVariant.value = 0
}

// History
const history = ref([])
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await posterAPI.history(1, 12)
    history.value = res.items || []
  } finally { historyLoading.value = false }
}

function viewHistory(item) {
  if (item.status === 'done' && item.variants?.length) {
    generationId.value = item.id
    generationDone.value = true
    variants.value = item.variants
    selectedVariant.value = 0
    generationError.value = ''
    progress.percent = 100
    form.brandName = item.brand_name
    form.eventKeyword = item.event_keyword
  } else if (item.status === 'processing') {
    generationId.value = item.id
    generationDone.value = false
    startProgressPolling(item.id)
  }
}

function downloadHistory(item) {
  const a = document.createElement('a')
  a.href = posterAPI.downloadUrl(item.id)
  a.download = `${item.brand_name}_${item.event_keyword}_poster.png`
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function styleLabel(v) {
  return styles.value.find(s => s.value === v)?.label || v || ''
}
function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  store.fetchMe().catch(() => {})
  loadHistory()
})
onUnmounted(closeEventSource)
</script>

<style scoped>
.poster-page { max-width: 960px; margin: 0 auto; color: var(--ybc-text); }

.back-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text-dim);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
  margin-bottom: 20px;
}
.back-btn:hover { background: rgba(255,255,255,0.04); color: var(--ybc-text); }

/* Hero */
.page-hero { text-align: center; margin-bottom: 28px; padding: 12px 0; }
.hero-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  background: rgba(236, 72, 153, 0.08);
  border: 1px solid rgba(236, 72, 153, 0.2);
  color: #f9a8d4;
  font-size: 11px; font-weight: 500;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}
.hero-badge .dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: #22c55e;
  animation: ybc-pulse-dot 2s infinite;
}
.page-hero h1 {
  font-size: 28px; font-weight: 800;
  color: var(--ybc-text-strong);
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.page-hero p {
  font-size: 14px;
  color: var(--ybc-text-dim);
}

/* Form */
.form-card, .progress-card, .result-card, .history-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
  padding: 28px 32px;
  margin-bottom: 18px;
  box-shadow: var(--ybc-shadow-md);
}

.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px; }
.row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin-bottom: 16px; }

.field { margin-bottom: 16px; }
.field label {
  display: block;
  font-size: 12px; font-weight: 600;
  color: var(--ybc-text);
  margin-bottom: 6px;
}
.req { color: var(--ybc-danger); }
.opt { color: var(--ybc-text-faint); font-weight: 400; font-size: 11px; margin-left: 4px; }

/* Keyword browser — categorized picker with search */
.kw-browser {
  margin-top: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 14px;
  overflow: hidden;
}

.kw-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 8px 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.kw-tabs::-webkit-scrollbar { display: none; }

.kw-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px;
  background: transparent;
  border: none;
  border-radius: 10px 10px 0 0;
  color: var(--ybc-text-dim);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
  white-space: nowrap;
  flex-shrink: 0;
  position: relative;
}
.kw-tab:hover { color: var(--ybc-text); background: rgba(255, 255, 255, 0.03); }
.kw-tab.active {
  color: var(--ybc-text-strong);
  background: rgba(236, 72, 153, 0.08);
}
.kw-tab.active::after {
  content: '';
  position: absolute;
  left: 14px; right: 14px; bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, #ec4899, #a855f7);
  border-radius: 2px 2px 0 0;
}
.kw-tab-icon { font-size: 14px; }
.kw-tab-count {
  font-size: 10px;
  color: var(--ybc-text-faint);
  background: rgba(255, 255, 255, 0.04);
  padding: 1px 6px;
  border-radius: 100px;
  font-weight: 600;
}
.kw-tab.active .kw-tab-count {
  background: rgba(236, 72, 153, 0.15);
  color: #f9a8d4;
}

.kw-search-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  border-top: 1px solid var(--ybc-border);
  background: rgba(0, 0, 0, 0.15);
}
.kw-search {
  flex: 1;
  padding: 7px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text);
  font-size: 12px;
  outline: none;
  font-family: inherit;
}
.kw-search:focus { border-color: rgba(236, 72, 153, 0.4); }
.kw-search::placeholder { color: var(--ybc-text-faint); }
.kw-hint {
  font-size: 11px;
  color: var(--ybc-text-muted);
  white-space: nowrap;
}

.kw-grid {
  display: flex; flex-wrap: wrap; gap: 6px;
  padding: 12px 14px 14px;
  max-height: 280px;
  overflow-y: auto;
}
.kw-grid::-webkit-scrollbar { width: 6px; }
.kw-grid::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
  border-radius: 3px;
}

.kw-item {
  padding: 5px 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--ybc-border);
  border-radius: 100px;
  color: var(--ybc-text-dim);
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.kw-item:hover {
  background: rgba(236, 72, 153, 0.1);
  color: #f9a8d4;
  border-color: rgba(236, 72, 153, 0.35);
  transform: translateY(-1px);
}
.kw-item.active {
  background: linear-gradient(135deg, rgba(236, 72, 153, 0.25), rgba(168, 85, 247, 0.25));
  color: #fff;
  border-color: rgba(236, 72, 153, 0.5);
  box-shadow: 0 0 0 1px rgba(236, 72, 153, 0.15);
}
.kw-empty {
  width: 100%;
  padding: 20px;
  text-align: center;
  font-size: 12px;
  color: var(--ybc-text-muted);
}

.field-input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  color: var(--ybc-text-strong);
  font-size: 14px;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}
.field-input:focus { border-color: var(--ybc-accent); background: rgba(99, 102, 241, 0.04); }
.field-input::placeholder { color: var(--ybc-text-faint); }

select.field-input {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2371717a'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}
select.field-input option { background: #12121a; color: var(--ybc-text); }

.color-input-row { display: flex; gap: 8px; align-items: center; }
.color-swatch {
  width: 38px; height: 38px;
  padding: 0; border: 1px solid var(--ybc-border);
  border-radius: 8px; cursor: pointer; background: transparent;
}
.color-hex { flex: 1; font-family: 'SF Mono', Menlo, monospace; }

/* Product uploader */
.product-uploader {
  position: relative;
  border: 1.5px dashed var(--ybc-border);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  transition: 0.15s;
  overflow: hidden;
  min-height: 140px;
  cursor: pointer;
}
.product-uploader:hover { border-color: rgba(236, 72, 153, 0.35); background: rgba(236, 72, 153, 0.03); }
.product-uploader.dragging {
  border-color: #ec4899;
  background: rgba(236, 72, 153, 0.08);
  border-style: solid;
}
.product-uploader.has-image {
  border-style: solid;
  border-color: rgba(34, 197, 94, 0.3);
  cursor: default;
}

.product-drop {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 28px 16px;
  text-align: center;
  color: var(--ybc-text-muted);
}
.product-drop-icon {
  color: var(--ybc-text-muted);
  margin-bottom: 10px;
  opacity: 0.7;
}
.product-drop-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--ybc-text);
  margin-bottom: 4px;
}
.product-drop-hint {
  font-size: 11px;
  color: var(--ybc-text-faint);
}

.product-preview {
  position: relative;
  padding: 12px;
  background: linear-gradient(135deg, #0a0a0f, #1a1a24);
  min-height: 160px;
  display: flex; align-items: center; justify-content: center;
}
.product-preview img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
  border-radius: 6px;
}
.product-overlay {
  position: absolute; top: 8px; right: 8px;
  display: flex; flex-direction: column; align-items: flex-end;
  gap: 6px;
}
.product-hint {
  display: inline-block;
  padding: 3px 8px;
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  border-radius: 100px;
  font-size: 11px;
  backdrop-filter: blur(8px);
}
.product-hint.ok {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
  border: 1px solid rgba(34, 197, 94, 0.3);
}
.product-remove {
  padding: 4px 10px;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 100px;
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  backdrop-filter: blur(8px);
}
.product-remove:hover { background: rgba(239, 68, 68, 0.25); color: #fff; }

.product-hint-below {
  font-size: 11px;
  color: var(--ybc-text-muted);
  margin-top: 6px;
}

/* Style grid */
.style-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.style-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  cursor: pointer;
  transition: 0.15s;
}
.style-card:hover { border-color: rgba(236, 72, 153, 0.35); background: rgba(236, 72, 153, 0.05); }
.style-card.selected {
  border-color: #ec4899;
  background: rgba(236, 72, 153, 0.1);
  box-shadow: 0 0 0 1px rgba(236, 72, 153, 0.25);
}
.style-icon { font-size: 22px; }
.style-label { font-size: 11px; font-weight: 600; color: var(--ybc-text); }

/* Credits */
.credit-row {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: rgba(245, 158, 11, 0.06);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 10px;
  color: #fcd34d;
  font-size: 13px;
  margin: 8px 0 16px;
}
.credit-row b { color: #fde68a; font-weight: 700; }
.insufficient {
  margin-left: auto;
  padding: 2px 8px;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  border-radius: 100px;
  font-size: 11px;
}

/* Buttons */
.generate-btn {
  width: 100%;
  padding: 14px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: linear-gradient(135deg, #ec4899 0%, #a855f7 50%, #6366f1 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px; font-weight: 600;
  cursor: pointer;
  transition: 0.2s;
  font-family: inherit;
}
.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 32px rgba(236, 72, 153, 0.35);
}
.generate-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Progress */
.progress-head {
  display: flex; align-items: center; gap: 10px;
  font-size: 15px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin-bottom: 14px;
}
.pulse {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #ec4899;
  animation: ybc-pulse-dot 1s infinite;
}
.progress-track {
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 100px;
  overflow: hidden;
  margin-bottom: 16px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #ec4899, #a855f7, #6366f1);
  background-size: 200% 100%;
  animation: stripe 2s linear infinite;
  transition: width 0.5s ease;
}
@keyframes stripe {
  0% { background-position: 0 0; }
  100% { background-position: 200% 0; }
}
.progress-steps { display: flex; justify-content: space-between; gap: 8px; }
.progress-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  flex: 1; opacity: 0.4; transition: 0.3s;
}
.progress-step.active, .progress-step.done { opacity: 1; }
.step-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
}
.progress-step.active .step-dot {
  background: #ec4899;
  box-shadow: 0 0 12px rgba(236, 72, 153, 0.6);
  animation: ybc-pulse-dot 1.2s infinite;
}
.progress-step.done .step-dot { background: #22c55e; }
.step-label { font-size: 11px; color: var(--ybc-text-dim); text-align: center; }

/* Error */
.error-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 12px;
  color: #fca5a5;
  font-size: 14px;
  margin-bottom: 18px;
}
.clear-btn {
  margin-left: auto; background: none; border: none;
  color: inherit; cursor: pointer; font-size: 16px;
  font-family: inherit;
}

/* Result */
.result-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--ybc-border);
}
.result-head h3 {
  font-size: 18px; font-weight: 700;
  color: var(--ybc-text-strong);
}
.ghost-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.ghost-btn:hover { border-color: var(--ybc-accent-light); color: var(--ybc-accent-light); }
.ghost-btn.small { padding: 5px 10px; font-size: 12px; }

.variant-wrapper {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}
.variant-item {
  cursor: pointer;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid var(--ybc-border);
  transition: 0.2s;
  background: rgba(255, 255, 255, 0.02);
}
.variant-item:hover { transform: translateY(-2px); border-color: rgba(236, 72, 153, 0.4); }
.variant-item.selected {
  border-color: #ec4899;
  box-shadow: 0 0 0 2px rgba(236, 72, 153, 0.25);
}
.variant-preview {
  /* Fixed canvas — show whole image regardless of aspect ratio
     (portrait/square/landscape all supported, no distortion) */
  aspect-ratio: 9 / 16;
  background:
    linear-gradient(135deg, #0a0a0f 0%, #1a1a24 100%);
  display: flex; align-items: center; justify-content: center;
  padding: 4px;
  position: relative;
  overflow: hidden;
}
.variant-preview::before {
  /* subtle checkerboard so transparent-ish PNGs are visible */
  content: '';
  position: absolute; inset: 0;
  background-image:
    linear-gradient(45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(255,255,255,0.02) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.02) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.02) 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  pointer-events: none;
}
.variant-preview img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;       /* show full image, no cropping/stretch */
  display: block;
  position: relative;
  z-index: 1;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
  border-radius: 4px;
}
.variant-label {
  padding: 8px; text-align: center;
  font-size: 12px; color: var(--ybc-text-dim);
  background: var(--ybc-surface-2);
}

.download-row {
  display: flex; gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--ybc-border);
}
.download-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  color: var(--ybc-text);
  font-size: 14px; font-weight: 500;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.download-btn:hover { background: rgba(99, 102, 241, 0.1); border-color: var(--ybc-accent-light); }
.download-btn.primary {
  background: var(--ybc-gradient-primary);
  border: none;
  color: #fff;
}
.download-btn.primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
}

/* History */
.history-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 14px;
}
.history-head h3 {
  font-size: 15px; font-weight: 700;
  color: var(--ybc-text-strong);
}
.history-empty {
  padding: 40px;
  text-align: center;
  color: var(--ybc-text-muted);
  font-size: 13px;
}
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 10px;
  cursor: pointer;
  transition: 0.15s;
}
.history-item:hover { background: rgba(99, 102, 241, 0.04); border-color: rgba(99, 102, 241, 0.2); }
.history-preview {
  width: 56px; height: 96px;
  border-radius: 6px;
  background: linear-gradient(135deg, #0a0a0f, #1a1a24);
  overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.history-preview img {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
}
.history-placeholder { font-size: 22px; color: var(--ybc-text-muted); }

.history-info { flex: 1; min-width: 0; }
.history-title {
  font-size: 14px; font-weight: 600;
  color: var(--ybc-text-strong);
  margin-bottom: 4px;
}
.history-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 11px;
  color: var(--ybc-text-muted);
  flex-wrap: wrap;
}
.history-meta .time { color: var(--ybc-text-faint); }
.status-chip {
  padding: 1px 8px;
  border-radius: 100px;
  font-weight: 600;
}
.status-chip.s-done       { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.status-chip.s-processing { background: rgba(245, 158, 11, 0.12); color: #fcd34d; }
.status-chip.s-failed     { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }

.history-dl {
  padding: 5px 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 8px;
  color: var(--ybc-accent-light);
  font-size: 11px;
  cursor: pointer;
  font-family: inherit;
  flex-shrink: 0;
}
.history-dl:hover { background: var(--ybc-accent); color: #fff; border-color: var(--ybc-accent); }

@media (max-width: 760px) {
  .row-2, .row-3 { grid-template-columns: 1fr; }
  .style-grid { grid-template-columns: repeat(3, 1fr); }
  .form-card, .progress-card, .result-card, .history-card { padding: 20px; }
  .page-hero h1 { font-size: 22px; }
  .chip-group { flex-direction: column; gap: 6px; }
  .chip-group-title { width: auto; padding-top: 0; }
}
</style>
