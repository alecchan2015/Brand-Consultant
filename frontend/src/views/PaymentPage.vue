<template>
  <div class="payment-page">
    <!-- Loading skeleton -->
    <div v-if="loading && !order" class="pay-card skeleton">
      <div class="sk-line sk-title"></div>
      <div class="sk-box">
        <div class="sk-row"><span class="sk-line sk-xs"></span><span class="sk-line sk-mid"></span></div>
        <div class="sk-row"><span class="sk-line sk-xs"></span><span class="sk-line sk-mid"></span></div>
        <div class="sk-row"><span class="sk-line sk-xs"></span><span class="sk-line sk-short"></span></div>
        <div class="sk-row"><span class="sk-line sk-xs"></span><span class="sk-line sk-mid"></span></div>
      </div>
      <div class="sk-line sk-btn"></div>
    </div>

    <div v-else-if="order" class="pay-card">
      <div class="pay-header">
        <h2>{{ $t('payment.title') }}</h2>
        <span class="status-chip" :class="`s-${order.status}`">
          <span class="dot"></span>{{ statusLabel(order.status) }}
        </span>
      </div>

      <div class="order-info">
        <div class="row"><span>{{ $t('payment.orderNo') }}</span><code>{{ order.order_no }}</code></div>
        <div class="row"><span>{{ $t('payment.planLabel') }}</span><b>{{ order.plan?.name }}</b></div>
        <div class="row"><span>{{ $t('payment.duration') }}</span>{{ $t('common.unit.days', { n: order.plan?.duration_days }) }}</div>
        <div class="row"><span>{{ $t('payment.method') }}</span>{{ channelLabel(order.channel) }}</div>
        <div class="row amount-row">
          <span>{{ $t('payment.amount') }}</span>
          <b class="amount">¥ {{ (order.amount_cents / 100).toFixed(2) }}</b>
        </div>
        <div class="row hint-row"><span>{{ $t('payment.expiresAt') }}</span>{{ formatDate(order.expires_at) }}</div>
      </div>

      <!-- Manual channel -->
      <div v-if="order.channel === 'manual' && ['pending', 'awaiting_confirm'].includes(order.status)" class="manual-panel">
        <div v-if="order.status === 'pending'" class="manual-hint">
          <p>{{ message || $t('payment.manual.hint') }}</p>
          <div class="steps">
            <div class="step"><span class="n">1</span><span v-html="$t('payment.manual.steps.1', { amount: (order.amount_cents / 100).toFixed(2) })"></span></div>
            <div class="step"><span class="n">2</span><span v-html="$t('payment.manual.steps.2', { orderNo: order.order_no })"></span></div>
            <div class="step"><span class="n">3</span>{{ $t('payment.manual.steps.3') }}</div>
            <div class="step"><span class="n">4</span>{{ $t('payment.manual.steps.4') }}</div>
          </div>
          <button class="primary-btn" :disabled="acting" @click="markPaying">
            {{ acting ? $t('payment.manual.submitting') : $t('payment.manual.paidBtn') }}
          </button>
        </div>
        <div v-else class="waiting-state">
          <div class="state-icon">⏳</div>
          <h3>{{ $t('payment.waiting.title') }}</h3>
          <p>{{ $t('payment.waiting.desc') }}</p>
          <p class="sub-hint">{{ $t('payment.waiting.hint') }}</p>
        </div>
      </div>

      <!-- Stripe -->
      <div v-else-if="order.channel === 'stripe' && order.status === 'pending'" class="channel-panel">
        <p class="channel-hint">{{ $t('payment.stripe.hint') }}</p>
        <a v-if="paymentUrl" :href="paymentUrl" class="primary-btn">{{ $t('payment.stripe.btn') }}</a>
      </div>

      <!-- Alipay / Wechat -->
      <div v-else-if="['alipay', 'wechat'].includes(order.channel) && order.status === 'pending'" class="channel-panel">
        <p class="channel-hint">{{ message || $t('payment.qr.hint') }}</p>
        <div v-if="qrCodeUrl" class="qr-box">
          <img :src="qrCodeUrl" alt="Payment QR" />
        </div>
        <div v-else class="qr-placeholder">
          <span class="q-icon">📱</span>
          <p>{{ $t('payment.qr.loading') }}</p>
          <p class="sub-hint">{{ $t('payment.qr.note') }}</p>
        </div>
      </div>

      <!-- Paid -->
      <div v-else-if="order.status === 'paid'" class="success-state">
        <div class="state-icon success-icon">✓</div>
        <h3>{{ $t('payment.success.title') }}</h3>
        <p>{{ $t('payment.success.desc', { paidAt: paidAtText }) }}</p>
        <button class="primary-btn" @click="$router.push('/membership')">{{ $t('payment.success.btn') }}</button>
      </div>

      <div v-else-if="['canceled', 'refunded', 'failed'].includes(order.status)" class="fail-state">
        <div class="state-icon">⚠️</div>
        <h3>{{ $t('payment.failState.title', { status: statusLabel(order.status) }) }}</h3>
        <button class="primary-btn" @click="$router.push('/membership')">{{ $t('payment.failState.btn') }}</button>
      </div>

      <div class="footer-actions">
        <button class="link-btn" @click="$router.push('/orders')">{{ $t('payment.myOrdersLink') }}</button>
        <button v-if="['pending'].includes(order.status)" class="link-btn danger" @click="cancelOrder">{{ $t('payment.cancelLink') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { paymentAPI } from '../api'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const order = ref(null)
const loading = ref(true)
const acting = ref(false)
const message = ref('')
const paymentUrl = ref('')
const qrCodeUrl = ref('')

function channelLabel(ch) {
  const key = `orders.channels.${ch}`
  const v = t(key)
  return v === key ? ch : v
}
function statusLabel(s) {
  const key = `orders.status.${s}`
  const v = t(key)
  return v === key ? s : v
}
function formatDate(s) {
  return s ? new Date(s).toLocaleString(locale.value) : ''
}

const paidAtText = computed(() =>
  order.value?.paid_at ? t('payment.success.paidAt', { t: formatDate(order.value.paid_at) }) : ''
)

async function load() {
  loading.value = true
  try {
    order.value = await paymentAPI.getOrder(route.params.order_no)
  } catch (e) {
    ElMessage.error(e.message || t('common.loading'))
    router.push('/membership')
  } finally { loading.value = false }
}

async function markPaying() {
  acting.value = true
  try {
    order.value = await paymentAPI.markPaying(route.params.order_no)
    ElMessage.success(t('payment.manual.paidOk'))
  } catch (e) { ElMessage.error(e.message || t('common.submitting')) }
  finally { acting.value = false }
}

async function cancelOrder() {
  try {
    await ElMessageBox.confirm(t('payment.cancelConfirm'), t('payment.cancelConfirmTitle'), { type: 'warning' })
    order.value = await paymentAPI.cancelOrder(route.params.order_no)
    ElMessage.success(t('payment.cancelOk'))
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || t('common.submitting'))
  }
}

onMounted(load)
</script>

<style scoped>
.payment-page {
  max-width: 600px;
  margin: 20px auto;
  color: var(--ybc-text);
}

.pay-card {
  background: var(--ybc-surface-1);
  border: 1px solid var(--ybc-border);
  border-radius: 20px;
  padding: 32px;
  box-shadow: var(--ybc-shadow-md);
}

/* Skeleton */
.pay-card.skeleton { display: flex; flex-direction: column; gap: 16px; }
.pay-card.skeleton .sk-line {
  height: 14px;
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.09) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: sk-shim 1.5s infinite linear;
  border-radius: 4px;
}
.sk-title { width: 140px; height: 20px; }
.sk-xs    { width: 60px; height: 11px; }
.sk-short { width: 80px; }
.sk-mid   { width: 120px; }
.sk-btn   { height: 48px; border-radius: 12px !important; width: 100%; margin-top: 8px; }
.sk-box {
  display: flex; flex-direction: column; gap: 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 12px;
  padding: 16px 20px;
}
.sk-row { display: flex; justify-content: space-between; align-items: center; }
@keyframes sk-shim {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.pay-header {
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 18px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--ybc-border);
}
.pay-header h2 {
  margin: 0;
  font-size: 18px; font-weight: 700;
  color: var(--ybc-text-strong);
}

.status-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px;
  border-radius: 100px;
  font-size: 11px; font-weight: 600;
}
.status-chip .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.s-pending,
.s-awaiting_confirm { background: rgba(245, 158, 11, 0.15); color: #fcd34d; }
.s-pending .dot,
.s-awaiting_confirm .dot { animation: ybc-pulse-dot 1s infinite; }
.s-paid { background: rgba(34, 197, 94, 0.15); color: #86efac; }
.s-canceled { background: rgba(255, 255, 255, 0.08); color: var(--ybc-text-muted); }
.s-refunded, .s-failed { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }

/* Order info */
.order-info {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--ybc-border);
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 22px;
}
.order-info .row {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 6px 0;
  font-size: 13px;
  color: var(--ybc-text);
}
.order-info .row > span:first-child { color: var(--ybc-text-muted); font-size: 12px; }
.order-info code {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 12px;
  background: rgba(99, 102, 241, 0.1);
  color: var(--ybc-accent-light);
  padding: 2px 8px;
  border-radius: 4px;
}
.amount-row {
  padding-top: 14px !important;
  margin-top: 6px;
  border-top: 1px solid var(--ybc-border);
}
.amount-row .amount {
  color: #fca5a5;
  font-size: 24px;
  font-weight: 700;
}
.hint-row {
  font-size: 11px;
  color: var(--ybc-text-faint);
}

/* Manual panel */
.manual-hint > p {
  font-size: 14px;
  color: var(--ybc-text-dim);
  margin: 0 0 16px;
  line-height: 1.6;
}
.steps {
  background: rgba(245, 158, 11, 0.06);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 20px;
}
.step {
  display: flex; align-items: center; gap: 10px;
  font-size: 13px;
  color: #fde68a;
  line-height: 1.8;
  padding: 4px 0;
}
.step .n {
  width: 20px; height: 20px;
  border-radius: 50%;
  background: rgba(245, 158, 11, 0.2);
  color: #fcd34d;
  font-size: 11px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.step code {
  background: rgba(0, 0, 0, 0.3);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-family: 'SF Mono', Menlo, monospace;
}
.step b { color: #fcd34d; }

.primary-btn {
  display: block;
  width: 100%;
  padding: 14px;
  background: var(--ybc-gradient-primary);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px; font-weight: 600;
  cursor: pointer;
  text-decoration: none;
  text-align: center;
  transition: 0.2s;
  font-family: inherit;
}
.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(99, 102, 241, 0.35);
}
.primary-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* States */
.waiting-state, .success-state, .fail-state, .channel-panel {
  text-align: center;
  padding: 24px 0;
}
.state-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.success-icon {
  width: 72px; height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #22c55e, #16a34a);
  color: #fff;
  font-size: 36px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 16px;
  box-shadow: 0 12px 24px rgba(34, 197, 94, 0.35);
}
.waiting-state h3,
.success-state h3,
.fail-state h3 {
  color: var(--ybc-text-strong);
  margin: 10px 0;
  font-size: 20px;
}
.waiting-state p, .success-state p, .fail-state p {
  color: var(--ybc-text-dim);
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 12px;
}
.sub-hint { color: var(--ybc-text-muted); font-size: 12px !important; }
.channel-hint {
  color: var(--ybc-text-dim);
  font-size: 14px;
  margin-bottom: 16px;
}

.qr-box, .qr-placeholder {
  width: 220px; height: 220px;
  margin: 20px auto;
  border-radius: 14px;
  background: #fff;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 14px;
}
.qr-placeholder {
  background: rgba(255, 255, 255, 0.04);
  border: 1px dashed var(--ybc-border);
}
.q-icon { font-size: 44px; color: var(--ybc-text-muted); }
.qr-placeholder p { color: var(--ybc-text-muted); font-size: 12px; margin-top: 8px; }
.qr-box img { width: 100%; height: 100%; object-fit: contain; }

.footer-actions {
  display: flex; justify-content: space-between;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--ybc-border);
}
.link-btn {
  background: none; border: none;
  font-size: 13px; cursor: pointer;
  padding: 4px 8px;
  color: var(--ybc-text-muted);
  font-family: inherit;
}
.link-btn:hover { color: var(--ybc-accent-light); }
.link-btn.danger:hover { color: #fca5a5; }
</style>
