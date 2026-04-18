<template>
  <div class="lang-switch" :class="{ open }">
    <button class="lang-trigger" @click.stop="toggle" :aria-label="$t('common.actions.submit')">
      <span class="lang-flag">{{ current.flag }}</span>
      <span class="lang-label">{{ current.label }}</span>
      <svg class="lang-caret" width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M2 4l3 3 3-3" stroke="currentColor" stroke-width="1.5"
          stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>
    <transition name="lang-pop">
      <div v-if="open" class="lang-menu" @click.stop>
        <button
          v-for="l in SUPPORTED_LOCALES"
          :key="l.code"
          class="lang-item"
          :class="{ active: l.code === locale }"
          @click="pick(l.code)"
        >
          <span class="lang-flag">{{ l.flag }}</span>
          <span>{{ l.label }}</span>
          <span v-if="l.code === locale" class="lang-check">✓</span>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { SUPPORTED_LOCALES, setLocale } from '../i18n'

const { locale } = useI18n()
const open = ref(false)

const current = computed(() =>
  SUPPORTED_LOCALES.find(l => l.code === locale.value) || SUPPORTED_LOCALES[0]
)

function toggle() { open.value = !open.value }
function pick(code) {
  setLocale(code)
  open.value = false
}

function handleClickOutside(e) {
  if (open.value && !e.target.closest('.lang-switch')) open.value = false
}
onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.lang-switch { position: relative; display: inline-block; }

.lang-trigger {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid var(--ybc-border, rgba(255,255,255,0.1));
  border-radius: 8px;
  color: var(--ybc-text-dim, #a1a1aa);
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
  font-family: inherit;
}
.lang-trigger:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--ybc-text, #e4e4e7);
  border-color: var(--ybc-accent-light, #818cf8);
}
.lang-flag { font-size: 14px; line-height: 1; }
.lang-label {
  font-size: 12px;
  white-space: nowrap;
}
.lang-caret {
  opacity: 0.6;
  transition: transform 0.2s;
}
.lang-switch.open .lang-caret { transform: rotate(180deg); }

.lang-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 160px;
  background: var(--ybc-surface-2, #1a1a24);
  border: 1px solid var(--ybc-border, rgba(255,255,255,0.1));
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.4);
  z-index: 1000;
}

.lang-item {
  display: flex; align-items: center; gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  color: var(--ybc-text-dim, #a1a1aa);
  font-size: 13px;
  text-align: left;
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
  transition: 0.15s;
}
.lang-item:hover {
  background: rgba(99, 102, 241, 0.1);
  color: var(--ybc-text-strong, #fff);
}
.lang-item.active {
  background: rgba(99, 102, 241, 0.15);
  color: var(--ybc-accent-light, #818cf8);
  font-weight: 600;
}
.lang-check { margin-left: auto; font-weight: 700; }

/* Pop animation */
.lang-pop-enter-active, .lang-pop-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}
.lang-pop-enter-from, .lang-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}

/* Hide label on narrow triggers */
@media (max-width: 540px) {
  .lang-label { display: none; }
}
</style>
