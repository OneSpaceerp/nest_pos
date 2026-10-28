<script setup lang="ts">
// Shopper surface. No ERP words, no staff data. The guest holds an opaque token for one store visit;
// the basket and its request key survive reloads so a retry after a lost response returns the same basket.
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NIcon from '@shared/components/NIcon.vue'
import NQty from '@shared/components/NQty.vue'
import NScanner from '@shared/components/NScanner.vue'
import NSheet from '@shared/components/NSheet.vue'
import NState from '@shared/components/NState.vue'
import NInstall from '@shared/components/NInstall.vue'
import NToasts from '@shared/components/NToasts.vue'
import { toast } from '@shared/components/toast'
import { ApiError, call, newKey } from '@shared/lib/api'
import { money, t } from '@shared/lib/i18n'
import { cycleTheme, toggleLanguage } from '@shared/app/surface'

const props = defineProps<{ root: HTMLElement }>()
const API = (m: string) => `nest_pos.api.client.${m}`
const STORE_KEY = 'nest_pos_customer:visit'

interface PriceView { status: string; item_code: string; item_name: string; image?: string; description?: string; uom: string; rate: number; currency: string; price_includes_tax: boolean | null; availability: 'in_stock' | 'low' | 'out' | null }
interface Line { item_code: string; item_name: string; qty: number; rate: number; image?: string }
interface Visit { token: string; outlet: string; register: string; currency: string; lines: Line[]; pendingKey: string | null; basket: string | null }

const visit = reactive<Visit>({ token: '', outlet: '', register: '', currency: 'USD', lines: [], pendingKey: null, basket: null })
const stage = ref<'choose' | 'store' | 'shop' | 'sent'>('choose')
const outlets = ref<{ register: string; outlet_label: string }[] | null>(null)
const scanning = ref(false)
const found = ref<PriceView | null>(null)
const foundQty = ref(1)
const sending = ref(false)
const status = ref<{ status: string; handoff_code: string; total_preview: number } | null>(null)
const error = ref('')
let pollTimer = 0

const total = computed(() => visit.lines.reduce((a, l) => a + l.qty * l.rate, 0))
const count = computed(() => visit.lines.reduce((a, l) => a + l.qty, 0))

function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(visit)) } catch { /* private mode */ }
}
watch(visit, save, { deep: true })

onMounted(async () => {
  try { Object.assign(visit, JSON.parse(localStorage.getItem(STORE_KEY) ?? '{}')) } catch { /* fresh visit */ }
  const storeCode = new URLSearchParams(location.search).get('store') ?? location.pathname.match(/\/customer\/s\/([^/]+)/)?.[1]
  if (storeCode) return start({ store_code: decodeURIComponent(storeCode) })
  if (visit.basket) {
    stage.value = 'sent'
    void refreshStatus()
  } else if (visit.token) stage.value = 'shop'
})
onBeforeUnmount(() => clearTimeout(pollTimer))

async function loadOutlets() {
  stage.value = 'store'
  try {
    outlets.value = await call(API('outlets'), {}, { method: 'GET' })
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function start(args: { register_name?: string; store_code?: string }) {
  try {
    const res = await call<{ token: string; outlet: string; register: string }>(API('start'), args)
    Object.assign(visit, { token: res.token, outlet: res.outlet, register: res.register, lines: visit.register === res.register ? visit.lines : [], basket: null, pendingKey: null })
    stage.value = 'shop'
    history.replaceState(null, '', '/nest-pos/customer/')
  } catch (e) {
    error.value = (e as Error).message
    stage.value = 'store'
  }
}

async function guarded<T>(fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn()
  } catch (e) {
    if (e instanceof ApiError && e.kind === 'permission') {
      toast(e.message, 'warn')
      Object.assign(visit, { token: '', basket: null, pendingKey: null })
      stage.value = 'store'
      void loadOutlets()
      return undefined
    }
    toast((e as Error).message, 'danger')
    return undefined
  }
}

async function onCode(code: string) {
  const res = await guarded(() => call<PriceView>(API('price'), { token: visit.token, code }))
  if (!res) return
  if (res.status !== 'ok') {
    toast(t('We couldn’t find that product. Ask a member of staff.'), 'warn')
    return
  }
  scanning.value = false
  visit.currency = res.currency
  found.value = res
  foundQty.value = 1
}

function addFound() {
  const f = found.value!
  const existing = visit.lines.find((l) => l.item_code === f.item_code)
  if (existing) existing.qty += foundQty.value
  else visit.lines.push({ item_code: f.item_code, item_name: f.item_name, qty: foundQty.value, rate: f.rate, image: f.image })
  found.value = null
}

async function send() {
  sending.value = true
  visit.pendingKey ??= newKey('basket-') // reused on retry: the server returns the same basket
  const res = await guarded(() =>
    call<{ basket: string; handoff_code: string; status: string; total_preview: number }>(API('submit'), {
      token: visit.token,
      lines: visit.lines.map((l) => ({ item_code: l.item_code, qty: l.qty })),
      request_key: visit.pendingKey,
    }, { timeoutMs: 20000 }),
  )
  sending.value = false
  if (!res) return
  visit.basket = res.basket
  visit.pendingKey = null
  status.value = res
  stage.value = 'sent'
  schedulePoll()
}

async function refreshStatus() {
  if (!visit.basket) return
  const res = await guarded(() => call<{ status: string; handoff_code: string; total_preview: number }>(API('status'), { token: visit.token, basket: visit.basket }))
  if (res) status.value = res
  schedulePoll()
}
function schedulePoll() {
  clearTimeout(pollTimer)
  if (status.value && ['Completed', 'Cancelled', 'Expired'].includes(status.value.status)) return
  pollTimer = window.setTimeout(refreshStatus, 4000)
}

async function cancelBasket() {
  const res = await guarded(() => call<{ status: string; handoff_code: string; total_preview: number }>(API('cancel'), { token: visit.token, basket: visit.basket }))
  if (res) status.value = res
}

function newBasket() {
  Object.assign(visit, { lines: [], basket: null, pendingKey: null })
  status.value = null
  stage.value = 'shop'
}

const STATUS_TEXT: Record<string, [string, string]> = {
  Submitted: ['Waiting for a cashier', 'Go to any till and show this code.'],
  Claimed: ['A cashier has your basket', 'They are checking your items now.'],
  Imported: ['Your basket is at the till', 'Pay at the till to finish.'],
  Completed: ['Paid — thank you', 'Your receipt comes from the till.'],
  Cancelled: ['This basket was cancelled', 'Start a new basket if you still want to buy.'],
  Expired: ['This basket expired', 'Baskets wait for an hour. Start a new one.'],
}
</script>

<template>
  <div class="cust">
    <header class="cust__top">
      <img src="/assets/nest_pos/images/nest-pos-logo.png" alt="" width="32" height="32" class="cust__logo" />
      <strong>{{ visit.outlet || 'Nest Shop' }}</strong>
      <span class="spacer" />
      <button type="button" class="cust__util" :aria-label="t('Language')" @click="toggleLanguage('nest_pos_customer', props.root)"><NIcon name="globe" /></button>
      <button type="button" class="cust__util" :aria-label="t('Theme')" @click="cycleTheme('nest_pos_customer', props.root)"><NIcon name="moon" /></button>
    </header>

    <main class="cust__main scroll">
      <section v-if="stage === 'choose'" class="cust__hero">
        <h1>{{ t('Scan, check prices, skip the wait') }}</h1>
        <p class="muted">{{ t('Build your basket on your phone and hand it to the till with one code.') }}</p>
        <NButton variant="primary" size="lg" icon="basket" block @click="loadOutlets">{{ t('I am shopping') }}</NButton>
        <a class="cust__staff" href="/nest-pos/sell">{{ t('I work here') }}</a>
      </section>

      <section v-else-if="stage === 'store'" class="cust__panel">
        <h1>{{ t('Which store are you in?') }}</h1>
        <p class="muted">{{ t('Or scan the store’s QR code at the entrance.') }}</p>
        <NState v-if="error" kind="error" :title="error" :retry="loadOutlets" />
        <NState v-else-if="!outlets" kind="loading" :title="t('Loading')" />
        <ul v-else class="cust__list" role="list">
          <li v-for="o in outlets" :key="o.register"><button type="button" class="cust__item" @click="start({ register_name: o.register })">{{ o.outlet_label }}<NIcon name="chevron" /></button></li>
        </ul>
      </section>

      <section v-else-if="stage === 'shop'" class="cust__panel">
        <NState v-if="!visit.lines.length" kind="empty" icon="scan" :title="t('Scan your first product')" :detail="t('You’ll see its price before adding it.')" />
        <ul v-else class="cust__lines" role="list">
          <li v-for="(l, i) in visit.lines" :key="l.item_code" class="cust__line">
            <span class="cust__line-name">{{ l.item_name }}<br /><span class="muted num">{{ money(l.rate, visit.currency) }}</span></span>
            <NQty :model-value="l.qty" :min="0" :label="t('Quantity of {0}', l.item_name)" @update:model-value="(v: number) => (v ? (l.qty = v) : visit.lines.splice(i, 1))" />
          </li>
        </ul>
      </section>

      <section v-else-if="stage === 'sent' && status" class="cust__panel cust__sent">
        <p class="cust__label">{{ t('Show this code at the till') }}</p>
        <p class="cust__code code" aria-live="polite">{{ status.handoff_code }}</p>
        <h2>{{ t(STATUS_TEXT[status.status]?.[0] ?? status.status) }}</h2>
        <p class="muted">{{ t(STATUS_TEXT[status.status]?.[1] ?? '') }}</p>
        <p class="num">{{ t('Estimated total') }} <strong>{{ money(status.total_preview, visit.currency) }}</strong></p>
        <p class="muted cust__small">{{ t('Prices are confirmed by the cashier. This is not a receipt.') }}</p>
        <NButton v-if="status.status === 'Submitted'" variant="ghost" @click="cancelBasket">{{ t('Cancel basket') }}</NButton>
        <NButton v-if="['Completed', 'Cancelled', 'Expired'].includes(status.status)" variant="primary" @click="newBasket">{{ t('Start a new basket') }}</NButton>
      </section>
    </main>

    <footer v-if="stage === 'shop'" class="cust__bar">
      <div class="cust__sum"><span class="num">{{ t('{0} items', count) }}</span><strong class="num">{{ money(total, visit.currency) }}</strong></div>
      <button type="button" class="cust__scan" :aria-label="t('Scan')" @click="scanning = true"><NIcon name="scan" :size="30" /></button>
      <NButton variant="primary" :busy="sending" :disabled="!visit.lines.length" @click="send">{{ t('Send basket to cashier') }}</NButton>
    </footer>

    <NSheet :open="scanning" :title="t('Check a price')" @close="scanning = false">
      <NScanner v-if="scanning" @code="onCode" @close="scanning = false" />
    </NSheet>

    <NSheet :open="!!found" :title="found?.item_name ?? ''" @close="found = null">
      <div v-if="found" class="cust__found">
        <img v-if="found.image" :src="found.image" alt="" class="cust__img" />
        <p class="cust__price num">{{ money(found.rate, found.currency) }} <span class="muted">/ {{ found.uom }}</span></p>
        <p v-if="found.price_includes_tax !== null" class="muted">{{ found.price_includes_tax ? t('Price includes tax') : t('Tax is added at the till') }}</p>
        <p v-if="found.availability === 'out'" class="cust__out">{{ t('Out of stock here') }}</p>
        <p v-else-if="found.availability === 'low'" class="muted">{{ t('Only a few left') }}</p>
        <p v-if="found.description" class="muted">{{ found.description }}</p>
        <NQty v-model="foundQty" :min="1" :label="t('Quantity')" />
      </div>
      <template #actions>
        <NButton @click="found = null; scanning = true">{{ t('Scan another') }}</NButton>
        <NButton variant="primary" icon="plus" :disabled="found?.availability === 'out'" @click="addFound">{{ t('Add to basket') }}</NButton>
      </template>
    </NSheet>
    <NToasts />
    <NInstall app="nest_pos_customer" name="Nest Shop" logo="/assets/nest_pos/images/nest-pos-logo.png" />
  </div>
</template>

<style>
.cust { display: flex; flex-direction: column; block-size: 100%; }
.cust__top { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) var(--space-4); min-block-size: 56px; background: var(--brand-fill); color: var(--brand-on-fill); }
.cust__logo { border-radius: 8px; box-shadow: 0 0 0 2px var(--nest-ink-900); }
.cust__util { inline-size: var(--touch); block-size: var(--touch); border: 0; background: transparent; color: inherit; display: grid; place-items: center; border-radius: var(--radius-md); cursor: pointer; }
.cust__main { flex: 1; min-block-size: 0; padding: var(--space-5) var(--space-4); }
.cust__hero, .cust__panel { max-inline-size: 520px; margin-inline: auto; display: grid; gap: var(--space-4); }
.cust__hero h1 { font-size: clamp(1.75rem, 1.2rem + 3vw, 2.5rem); line-height: 1.1; }
.cust__staff { text-align: center; color: var(--text-body); font-weight: 600; min-block-size: var(--touch); display: grid; place-items: center; }
.cust__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.cust__item { inline-size: 100%; display: flex; justify-content: space-between; align-items: center; min-block-size: var(--touch-lg); padding-inline: var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--border-subtle); background: var(--surface-card); color: var(--text-strong); font-weight: 600; cursor: pointer; }
.cust__lines { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.cust__line { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); padding: var(--space-3); background: var(--surface-card); border-radius: var(--radius-md); }
.cust__line-name { font-weight: 600; color: var(--text-strong); overflow-wrap: anywhere; }
.cust__bar { display: grid; grid-template-columns: 1fr auto 1fr; gap: var(--space-3); align-items: center; padding: var(--space-2) var(--space-3) calc(var(--space-2) + var(--safe-bottom)); background: var(--surface-card); border-block-start: 1px solid var(--border-subtle); }
.cust__sum { display: grid; font-size: var(--text-sm); }
.cust__sum strong { font-size: var(--text-lg); color: var(--text-strong); }
.cust__scan { inline-size: 68px; block-size: 68px; border-radius: 50%; border: 0; background: var(--action-primary-bg); color: var(--action-primary-fg); display: grid; place-items: center; margin-block-start: -24px; box-shadow: var(--shadow-overlay); cursor: pointer; }
.cust__sent { text-align: center; justify-items: center; }
.cust__label { font-weight: 600; }
.cust__code { font-size: clamp(3rem, 14vw, 4.5rem); font-weight: 700; letter-spacing: 0.16em; background: var(--brand-fill); color: var(--brand-on-fill); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-5); }
.cust__small { font-size: var(--text-sm); }
.cust__found { display: grid; gap: var(--space-3); justify-items: start; }
.cust__img { inline-size: 100%; max-block-size: 220px; object-fit: contain; border-radius: var(--radius-md); background: var(--surface-sunken); }
.cust__price { font-size: var(--text-2xl); font-weight: 700; color: var(--text-strong); }
.cust__out { color: var(--danger-fg); font-weight: 600; }
@media (max-width: 380px) { .cust__bar { grid-template-columns: 1fr auto; } .cust__sum { display: none; } }
</style>
