<template>
  <div class="orders-page">
    <div class="page-header">
      <h1>{{ $t('orders.title') }}</h1>
      <button class="refresh-btn" @click="load" :disabled="loading">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"
          :style="{ animation: loading ? 'spin 1s linear infinite' : '' }">
          <path d="M13 3v4h-4M3 13v-4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M4.2 6a5 5 0 018-1.5L13 7M11.8 10a5 5 0 01-8 1.5L3 9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>{{ $t('common.refresh') }}</span>
      </button>
    </div>

    <div v-if="!loading && !orders.length" class="empty-state">
      <div class="empty-icon">📭</div>
      <h3>{{ $t('orders.empty.title') }}</h3>
      <p>{{ $t('orders.empty.desc') }}</p>
      <button class="primary-btn" @click="$router.push('/membership')">{{ $t('orders.empty.cta') }}</button>
    </div>

    <div v-else class="order-list" :class="{ loading }">
      <div v-for="o in orders" :key="o.id"
        class="order-item" :class="{ clickable: isClickable(o.status) }"
        @click="isClickable(o.status) && $router.push(`/payment/${o.order_no}`)">
        <div class="main-row">
          <div class="left">
            <div class="plan-name">{{ o.plan?.name }}</div>
            <div class="order-no">{{ o.order_no }}</div>
          </div>
          <div class="right">
            <div class="amount">¥ {{ (o.amount_cents / 100).toFixed(2) }}</div>
            <span class="status-chip" :class="`s-${o.status}`">
              <span class="dot"></span>{{ statusLabel(o.status) }}
            </span>
          </div>
        </div>
        <div class="meta-row">
          <span class="meta-item">
            <span class="tier-chip" :class="`tier-${o.plan?.tier}`">
              {{ o.plan?.tier?.toUpperCase() }}
            </span>
            · {{ $t('common.unit.days', { n: o.plan?.duration_days }) }}
          </span>
          <span class="meta-item">{{ channelLabel(o.channel) }}</span>
          <span class="meta-item time">{{ formatDate(o.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { paymentAPI } from '../api'

const { t, locale } = useI18n()

const orders = ref([])
const loading = ref(false)

function channelLabel(c) { return t(`orders.channels.${c}`) !== `orders.channels.${c}` ? t(`orders.channels.${c}`) : c }
function isClickable(s) { return ['pending', 'awaiting_confirm'].includes(s) }
function statusLabel(s) { return t(`orders.status.${s}`) !== `orders.status.${s}` ? t(`orders.status.${s}`) : s }
function formatDate(s) {
  if (!s) return ''
  return new Date(s).toLocaleString(locale.value)
}

async function load() {
  loading.value = true
  try { orders.value = await paymentAPI.myOrders() }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.orders-page {
  max-width: 900px;
  margin: 0 auto;
  color: var(--ybc-text);
}

.page-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 22px; font-weight: 800;
  color: var(--ybc-text-strong);
  letter-spacing: -0.3px;
  margin: 0;
}

.refresh-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px;
  background: transparent;
  border: 1px solid var(--ybc-border);
  border-radius: 8px;
  color: var(--ybc-text-dim);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: 0.15s;
}
.refresh-btn:hover {
  background: rgba(99, 102, 241, 0.08);
  color: var(--ybc-accent-light);
  border-color: var(--ybc-accent-light);
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  text-align: center;
  padding: 80px 20px;
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
}
.empty-icon { font-size: 56px; margin-bottom: 16px; }
.empty-state h3 {
  font-size: 18px;
  color: var(--ybc-text-strong);
  margin-bottom: 8px;
}
.empty-state p {
  color: var(--ybc-text-dim);
  margin-bottom: 20px;
}
.primary-btn {
  padding: 10px 28px;
  background: var(--ybc-gradient-primary);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 14px; font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: 0.2s;
}
.primary-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4); }

/* Order list */
.order-list {
  display: flex; flex-direction: column;
  gap: 10px;
}
.order-list.loading { opacity: 0.6; pointer-events: none; }

.order-item {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 14px;
  padding: 16px 20px;
  transition: 0.15s;
}
.order-item.clickable { cursor: pointer; }
.order-item.clickable:hover {
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-1px);
}

.main-row {
  display: flex; justify-content: space-between; align-items: center;
  gap: 16px;
}
.left { min-width: 0; flex: 1; }
.right { text-align: right; }

.plan-name {
  font-size: 15px; font-weight: 700;
  color: var(--ybc-text-strong);
  margin-bottom: 4px;
}
.order-no {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 11px;
  color: var(--ybc-text-faint);
}

.amount {
  font-size: 18px; font-weight: 700;
  color: #fca5a5;
  margin-bottom: 4px;
}

.status-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 2px 10px;
  border-radius: 100px;
  font-size: 11px; font-weight: 600;
}
.status-chip .dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.s-pending, .s-awaiting_confirm { background: rgba(245, 158, 11, 0.12); color: #fcd34d; }
.s-pending .dot, .s-awaiting_confirm .dot { animation: ybc-pulse-dot 1s infinite; }
.s-paid { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.s-canceled { background: rgba(255, 255, 255, 0.06); color: var(--ybc-text-muted); }
.s-refunded, .s-failed { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }

.meta-row {
  display: flex; align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--ybc-border);
  font-size: 11px;
  color: var(--ybc-text-muted);
  flex-wrap: wrap;
}
.meta-item { display: inline-flex; align-items: center; gap: 6px; }
.meta-item.time { margin-left: auto; color: var(--ybc-text-faint); }

.tier-chip {
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 10px; font-weight: 700;
  color: #fff;
  letter-spacing: 0.5px;
}
.tier-chip.tier-vip   { background: linear-gradient(135deg, #3b82f6, #6366f1); }
.tier-chip.tier-vvip  { background: linear-gradient(135deg, #8b5cf6, #ec4899); }
.tier-chip.tier-vvvip { background: linear-gradient(135deg, #f59e0b, #ef4444); }

@media (max-width: 640px) {
  .main-row { flex-direction: column; align-items: flex-start; }
  .right { text-align: left; }
  .meta-item.time { margin-left: 0; }
}
</style>
