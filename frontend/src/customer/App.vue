<script setup lang="ts">
// Nest Shop: the shopper app. Four places, one thumb away: Home, Scan (the big button in the middle),
// Basket and Account. Works without an account; signing in keeps receipts and lets the till know who
// is buying. No ERP words, no staff data; guest calls carry an opaque visit token only.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NIcon from '@shared/components/NIcon.vue'
import NQty from '@shared/components/NQty.vue'
import NScanner from '@shared/components/NScanner.vue'
import NSheet from '@shared/components/NSheet.vue'
import NState from '@shared/components/NState.vue'
import NInstall from '@shared/components/NInstall.vue'
import NToasts from '@shared/components/NToasts.vue'
import { toast } from '@shared/components/toast'
import { call } from '@shared/lib/api'
import { money, t } from '@shared/lib/i18n'
import { cycleTheme, toggleLanguage } from '@shared/app/surface'
import AccountTab from './views/AccountTab.vue'
import BasketTab from './views/BasketTab.vue'
import HomeTab from './views/HomeTab.vue'
import { API, accountMode, addToBasket, checkPrice, count, needsStore, refreshStatus, startVisit, status, stopPolling, visit, type PriceView } from './visit'

const props = defineProps<{ root: HTMLElement }>()
const LOGO = '/assets/nest_pos/images/nest-pos-logo.png?v=7ea748eb'

type Tab = 'home' | 'basket' | 'account'
const TABS: Tab[] = ['home', 'basket', 'account']
const fromHash = (h: string): Tab | null => (TABS.includes(h as Tab) ? (h as Tab) : h === 'signin' || h === 'signup' ? 'account' : null)
const tab = ref<Tab>(fromHash(location.hash.slice(1)) ?? 'home')
watch(tab, (v) => history.replaceState(null, '', `${location.pathname}${location.search}#${v}`))
const onHash = () => {
  const h = location.hash.slice(1)
  if (h === 'signin' || h === 'signup') accountMode.value = h
  const next = fromHash(h)
  if (next) tab.value = next
}

// ---- scanning and the product sheet
const scanning = ref(false)
const found = ref<PriceView | null>(null)
const foundQty = ref(1)
function openScanner() {
  if (!visit.token) return void (needsStore.value = true)
  scanning.value = true
}
async function onCode(code: string) {
  const res = await checkPrice(code)
  if (!res) return
  scanning.value = false
  showProduct(res)
}
function showProduct(p: PriceView) {
  found.value = p
  foundQty.value = 1
}
function addFound() {
  if (found.value && addToBasket(found.value, foundQty.value)) {
    toast(t('{0} added to your basket', found.value.item_name))
    found.value = null
  }
}

// ---- store picker (first visit, expired visit or "change store")
const outlets = ref<{ register: string; outlet_label: string }[] | null>(null)
const storeError = ref('')
watch(needsStore, (v) => v && void loadOutlets(), { immediate: true })
async function loadOutlets() {
  storeError.value = ''
  try {
    outlets.value = await call(API('outlets'), {}, { method: 'GET' })
  } catch (e) {
    storeError.value = (e as Error).message
  }
}
async function pickStore(register: string) {
  try {
    await startVisit({ register_name: register })
  } catch (e) {
    toast((e as Error).message, 'danger')
  }
}

onMounted(async () => {
  window.addEventListener('hashchange', onHash)
  const storeCode = new URLSearchParams(location.search).get('store') ?? location.pathname.match(/\/customer\/s\/([^/]+)/)?.[1]
  if (storeCode) {
    try {
      await startVisit({ store_code: decodeURIComponent(storeCode) })
      history.replaceState(null, '', `/nest-pos/customer/#${tab.value}`)
    } catch (e) {
      toast((e as Error).message, 'danger')
      needsStore.value = true
    }
  } else if (!visit.token) needsStore.value = true
  if (visit.basket) void refreshStatus()
})
onBeforeUnmount(() => {
  window.removeEventListener('hashchange', onHash)
  stopPolling()
})

const basketBadge = computed(() => (visit.basket && status.value && !['Completed', 'Cancelled', 'Expired'].includes(status.value.status) ? '•' : count.value ? String(count.value) : ''))
</script>

<template>
  <div class="shop">
    <header class="shop__top">
      <img :src="LOGO" alt="" width="34" height="34" class="shop__logo" />
      <button type="button" class="shop__store" :aria-label="t('Change store')" @click="needsStore = true">
        <span class="shop__store-label" dir="auto">{{ visit.outlet || t('Choose your store') }}</span>
        <NIcon name="chevron" :size="16" class="shop__store-chev" />
      </button>
      <button type="button" class="shop__util" :aria-label="t('Language')" @click="toggleLanguage('nest_pos_customer', props.root)"><NIcon name="globe" /></button>
      <button type="button" class="shop__util" :aria-label="t('Theme')" @click="cycleTheme('nest_pos_customer', props.root)"><NIcon name="moon" /></button>
    </header>

    <main class="shop__main scroll">
      <HomeTab v-if="tab === 'home'" @scan="openScanner" @product="showProduct" @go="(v: Tab) => (tab = v)" />
      <BasketTab v-else-if="tab === 'basket'" @scan="openScanner" />
      <AccountTab v-else @go="(v: Tab) => (tab = v)" />
    </main>

    <nav class="shop__tabs" :aria-label="t('Sections')">
      <button type="button" :class="['shop__tab', { 'shop__tab--on': tab === 'home' }]" :aria-current="tab === 'home' ? 'page' : undefined" @click="tab = 'home'"><NIcon name="register" /><span>{{ t('Home') }}</span></button>
      <button type="button" :class="['shop__tab', { 'shop__tab--on': tab === 'basket' }]" :aria-current="tab === 'basket' ? 'page' : undefined" @click="tab = 'basket'">
        <span class="shop__tab-icon"><NIcon name="basket" /><span v-if="basketBadge" class="shop__badge num">{{ basketBadge }}</span></span><span>{{ t('Basket') }}</span>
      </button>
      <button type="button" class="shop__fab" :aria-label="t('Scan a product')" @click="openScanner"><NIcon name="scan" :size="30" /></button>
      <button type="button" :class="['shop__tab', { 'shop__tab--on': tab === 'account' }]" :aria-current="tab === 'account' ? 'page' : undefined" @click="tab = 'account'"><NIcon name="user" /><span>{{ t('Account') }}</span></button>
    </nav>

    <NSheet :open="scanning" :title="t('Check a price')" @close="scanning = false">
      <NScanner v-if="scanning" @code="onCode" @close="scanning = false" />
    </NSheet>

    <NSheet :open="!!found" :title="found?.item_name ?? ''" @close="found = null">
      <div v-if="found" class="shop__product">
        <div class="shop__product-img"><img v-if="found.image" :src="found.image" alt="" /><NIcon v-else name="image" :size="40" /></div>
        <p class="shop__product-price num">{{ money(found.rate, found.currency) }} <small class="muted">/ {{ found.uom }}</small></p>
        <p class="shop__product-tags">
          <span v-if="found.availability === 'out'" class="shop__tag shop__tag--out">{{ t('Out of stock here') }}</span>
          <span v-else-if="found.availability === 'low'" class="shop__tag shop__tag--low">{{ t('Only a few left') }}</span>
          <span v-else-if="found.availability === 'in_stock'" class="shop__tag shop__tag--ok">{{ t('In stock') }}</span>
          <span v-if="found.price_includes_tax !== null" class="shop__tag">{{ found.price_includes_tax ? t('Price includes tax') : t('Tax is added at the till') }}</span>
        </p>
        <p v-if="found.description" class="muted">{{ found.description }}</p>
        <label class="shop__qty">{{ t('Quantity') }} <NQty v-model="foundQty" :min="1" :label="t('Quantity')" /></label>
      </div>
      <template #actions>
        <NButton icon="scan" @click="found = null; openScanner()">{{ t('Scan another') }}</NButton>
        <NButton variant="primary" icon="plus" :disabled="found?.availability === 'out'" @click="addFound">{{ t('Add to basket') }}</NButton>
      </template>
    </NSheet>

    <NSheet :open="needsStore" :title="t('Which store are you in?')" :dismissible="!!visit.token" @close="needsStore = false">
      <p class="muted shop__store-hint">{{ t('Or scan the QR code at the store entrance with your camera.') }}</p>
      <NState v-if="storeError" kind="error" :title="storeError" :retry="loadOutlets" />
      <NState v-else-if="!outlets" kind="loading" :title="t('Loading')" />
      <NState v-else-if="!outlets.length" kind="empty" icon="basket" :title="t('No store is taking baskets right now')" />
      <ul v-else class="shop__stores" role="list">
        <li v-for="o in outlets" :key="o.register">
          <button type="button" :class="['shop__store-row', { 'shop__store-row--on': o.register === visit.register }]" @click="pickStore(o.register)">
            <NIcon name="basket" /><span>{{ o.outlet_label }}</span><NIcon v-if="o.register === visit.register" name="check" />
          </button>
        </li>
      </ul>
    </NSheet>

    <NToasts />
    <NInstall app="nest_pos_customer" name="Nest Shop" :logo="LOGO" />
  </div>
</template>

<style>
.shop { display: flex; flex-direction: column; block-size: 100%; background: var(--surface-page); }
.shop__top { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); min-block-size: 60px; background: var(--brand-fill); color: var(--brand-on-fill); }
.shop__logo { border-radius: 9px; box-shadow: 0 0 0 2px var(--nest-ink-900); flex: none; }
.shop__store { flex: 1; min-inline-size: 0; display: inline-flex; align-items: center; gap: 4px; border: 0; background: rgb(255 255 255 / 0.45); color: inherit; min-block-size: 40px; padding-inline: var(--space-3); border-radius: var(--radius-pill); font: inherit; font-weight: 700; cursor: pointer; justify-self: start; max-inline-size: max-content; }
.shop__store-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.shop__store-chev { transform: rotate(90deg); }
.shop__util { inline-size: var(--touch); block-size: var(--touch); border: 0; background: transparent; color: inherit; display: grid; place-items: center; border-radius: var(--radius-md); cursor: pointer; flex: none; }
.shop__top > .shop__util:first-of-type { margin-inline-start: auto; }
.shop__main { flex: 1; min-block-size: 0; padding: var(--space-4) var(--space-4) var(--space-6); }
.shop__main > * { max-inline-size: 560px; margin-inline: auto; }

.shop__tabs { position: relative; display: grid; grid-template-columns: 1fr 1fr 84px 1fr; align-items: end; background: var(--surface-card); border-block-start: 1px solid var(--border-subtle); padding: 6px var(--space-2) calc(6px + var(--safe-bottom)); }
.shop__tab { display: grid; justify-items: center; gap: 2px; min-block-size: 52px; border: 0; background: none; color: var(--text-muted); font: inherit; font-size: var(--text-xs); font-weight: 600; cursor: pointer; border-radius: var(--radius-md); }
.shop__tab--on { color: var(--text-strong); }
.shop__tab--on .n-icon { background: var(--brand-fill); color: var(--brand-on-fill); border-radius: var(--radius-pill); padding: 2px 14px; box-sizing: content-box; }
.shop__tab-icon { position: relative; display: inline-grid; }
.shop__badge { position: absolute; inset-block-start: -6px; inset-inline-end: -12px; min-inline-size: 20px; block-size: 20px; padding-inline: 5px; border-radius: 10px; background: var(--danger-fg); color: #fff; font-size: 11px; font-weight: 700; display: grid; place-items: center; }
/* the scan button sits in the bar, raised: the one thing people come here to do */
.shop__fab { justify-self: center; inline-size: 70px; block-size: 70px; margin-block-start: -34px; border-radius: 50%; border: 5px solid var(--surface-page); background: var(--action-primary-bg); color: var(--action-primary-fg); display: grid; place-items: center; cursor: pointer; box-shadow: var(--shadow-overlay); }

.shop__product { display: grid; gap: var(--space-3); }
.shop__product-img { aspect-ratio: 4 / 3; max-block-size: 240px; display: grid; place-items: center; background: var(--surface-sunken); border-radius: var(--radius-lg); overflow: hidden; color: var(--text-muted); }
.shop__product-img img { inline-size: 100%; block-size: 100%; object-fit: contain; }
.shop__product-price { font-size: var(--text-2xl); font-weight: 700; color: var(--text-strong); }
.shop__product-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.shop__tag { font-size: var(--text-xs); font-weight: 600; padding: 3px 10px; border-radius: var(--radius-pill); background: var(--surface-sunken); color: var(--text-body); }
.shop__tag--ok { background: var(--ok-bg); color: var(--ok-fg); }
.shop__tag--low { background: var(--warn-bg); color: var(--warn-fg); }
.shop__tag--out { background: var(--danger-bg); color: var(--danger-fg); }
.shop__qty { display: inline-flex; align-items: center; gap: var(--space-3); font-weight: 600; }
.shop__store-hint { margin-block-end: var(--space-3); }
.shop__stores { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.shop__store-row { inline-size: 100%; display: flex; align-items: center; gap: var(--space-3); min-block-size: var(--touch-lg); padding-inline: var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--border-subtle); background: var(--surface-card); color: var(--text-strong); font: inherit; font-weight: 600; cursor: pointer; text-align: start; }
.shop__store-row span { flex: 1; }
.shop__store-row--on { border-color: var(--text-strong); box-shadow: inset 0 0 0 1px var(--text-strong); }
</style>
