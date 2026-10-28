<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NIcon from '@shared/components/NIcon.vue'
import NScanner from '@shared/components/NScanner.vue'
import NSheet from '@shared/components/NSheet.vue'
import { toast } from '@shared/components/toast'
import { ApiError, call } from '@shared/lib/api'
import { money, t } from '@shared/lib/i18n'
import { on } from '@shared/lib/realtime'
import type { ScanOutcome } from '@shared/lib/scan'
import CartTape from '@shared/till/CartTape.vue'
import CatalogPanel from '@shared/till/CatalogPanel.vue'
import PaySheet from '@shared/till/PaySheet.vue'
import { receiptUrl } from '@shared/till/till'
import { useTill } from '../state'

const till = useTill()
const currency = computed(() => till.register.value?.currency ?? 'USD')
const due = computed(() => (till.quote.value && till.quoteState.value === 'fresh' ? till.quote.value.amount_due : Number(till.preview.value.total)))

const scanning = ref(false)
const scanFeedback = ref<{ tone: 'ok' | 'danger'; text: string } | null>(null)
const tapeOpen = ref(false) // phone: the cart is a sheet
const paying = ref(false)
const payBusy = ref(false)
const payError = ref('')
const receipt = ref<{ invoice?: { name: string; doctype?: string; amount_due: number }; change?: string; mode: 'online' | 'queued' } | null>(null)
const held = ref<{ name: string; label: string; total_preview: number; creation: string }[] | null>(null)
const customerOpen = ref(false)
const customerQuery = ref('')
const customers = ref<{ name: string; customer_name: string }[]>([])
const choice = ref<{ code: string; candidates: string[]; kind: 'ambiguous' | 'variant' } | null>(null)

async function handleScan(code: string) {
  let result: ScanOutcome
  try {
    result = await till.scan(code)
  } catch (e) {
    scanFeedback.value = { tone: 'danger', text: (e as Error).message }
    return
  }
  if (result.status === 'ok') {
    scanFeedback.value = { tone: 'ok', text: `${result.item_name} +${result.qty}` }
  } else if (result.status === 'ambiguous') {
    choice.value = { code: result.code, candidates: result.candidates, kind: 'ambiguous' }
  } else if (result.status === 'variant_required') {
    choice.value = { code: result.item_code, candidates: result.variants, kind: 'variant' }
  } else {
    const text = result.status === 'unknown' ? t('No product for code {0}', result.code) : (result as { message?: string }).message ?? t('Not found')
    scanFeedback.value = { tone: 'danger', text }
    navigator.vibrate?.([60, 40, 60])
    if (!scanning.value) toast(text, 'warn')
  }
  setTimeout(() => (scanFeedback.value = null), 1600)
}

function pick(itemCode: string) {
  const item = till.catalog.value.find((i) => i.item_code === itemCode)
  if (item) till.addItem(item)
  else void handleScan(itemCode)
  choice.value = null
}

async function pay(tenders: { mode_of_payment: string; amount: string }[]) {
  payBusy.value = true
  payError.value = ''
  try {
    const res = await till.submit(tenders)
    paying.value = false
    tapeOpen.value = false
    receipt.value = res as typeof receipt.value
    if (res.mode === 'queued') toast(t('Saved on this device — will sync when online'), 'info')
    else if ((res as { status: string }).status === 'needs_review') toast(t('The sale was kept for a manager to review.'), 'warn')
  } catch (e) {
    payError.value = e instanceof ApiError ? e.message : String(e)
  } finally {
    payBusy.value = false
  }
}

function printReceipt() {
  const inv = receipt.value?.invoice
  if (!inv) return
  window.open(receiptUrl(till.register.value, inv.doctype ?? 'Sales Invoice', inv.name), '_blank', 'noopener')
}

async function hold() {
  try {
    await call(till.api('hold_cart'), { register_name: till.registerName.value, cart: { ...till.payload(), total_preview: due.value }, label: till.cart.customer ?? '' })
    till.clearCart()
    toast(t('Sale held'))
  } catch (e) {
    toast((e as Error).message, 'danger')
  }
}

async function showHeld() {
  held.value = await call(till.api('held_carts'), { register_name: till.registerName.value }, { method: 'GET' })
}

async function resume(name: string) {
  if (till.cart.lines.length) return toast(t('Finish or hold the current sale first.'), 'warn')
  const { cart } = await call<{ cart: { lines: { item_code: string; qty: number; uom?: string }[]; customer: string | null } }>(till.api('resume_cart'), { name })
  for (const l of cart.lines) {
    const item = till.catalog.value.find((i) => i.item_code === l.item_code)
    till.addItem(item ?? { item_code: l.item_code, item_name: l.item_code, rate: null }, l.qty)
  }
  till.cart.customer = cart.customer
  held.value = null
}

let searchTimer = 0
function searchCustomers() {
  clearTimeout(searchTimer)
  searchTimer = window.setTimeout(async () => {
    const q = customerQuery.value.trim()
    customers.value = q
      ? await call('frappe.client.get_list', { doctype: 'Customer', filters: [['disabled', '=', 0]], or_filters: [['customer_name', 'like', `%${q}%`], ['mobile_no', 'like', `%${q}%`], ['name', 'like', `%${q}%`]], fields: ['name', 'customer_name'], limit_page_length: 12 }, { method: 'POST' })
      : []
  }, 250)
}

// a paired phone scans into *this* cart only (matched by cart id on the server and here)
let off: (() => void) | undefined
onMounted(() => {
  off = on('nest_pos:paired_scan', (data) => {
    const d = data as { cart_id: string; result: ScanOutcome }
    if (d.cart_id !== till.cart.id || d.result.status !== 'ok') return
    const r = d.result
    const item = till.catalog.value.find((i) => i.item_code === r.item_code)
    till.addItem({ item_code: r.item_code, item_name: r.item_name, rate: r.rate ?? item?.rate ?? null, uom: r.uom ?? null }, Number(r.qty) || 1)
    toast(t('{0} added from phone', r.item_name))
  })
})
onBeforeUnmount(() => off?.())
</script>

<template>
  <div class="sell">
    <CatalogPanel
      :items="till.catalog.value"
      :currency="currency"
      :state="till.catalogState.value"
      @pick="(i) => till.addItem(i)"
      @scan="handleScan"
      @camera="scanning = true"
    />
    <CartTape class="sell__tape" :till="till" @pay="paying = true" @hold="hold" @customer="customerOpen = true" @held="showHeld" />

    <!-- phone: thumb bar -->
    <div class="sell__bar">
      <button type="button" class="sell__bar-basket" :aria-label="t('Current sale: {0} items, {1}', till.itemCount.value, money(due, currency))" @click="tapeOpen = true">
        <NIcon name="basket" />
        <span class="sell__bar-sum">
          <span class="sell__bar-count">{{ t('{0} items', till.itemCount.value) }}</span>
          <strong class="num">{{ money(due, currency) }}</strong>
        </span>
      </button>
      <button type="button" class="sell__bar-scan" :aria-label="t('Scan')" @click="scanning = true"><NIcon name="scan" :size="30" /></button>
      <NButton variant="primary" :disabled="!till.cart.lines.length" @click="paying = true">{{ t('Pay') }}</NButton>
    </div>

    <NSheet :open="tapeOpen" :title="t('Current sale')" @close="tapeOpen = false">
      <CartTape :till="till" @pay="paying = true" @hold="hold" @customer="customerOpen = true" @held="tapeOpen = false; showHeld()" />
    </NSheet>

    <NSheet :open="scanning" :title="t('Scan')" wide @close="scanning = false">
      <NScanner v-if="scanning" continuous :feedback="scanFeedback" @code="handleScan" @close="scanning = false" />
      <p class="muted sell__scan-total">{{ t('{0} items', till.itemCount.value) }} · <span class="num">{{ money(due, currency) }}</span></p>
    </NSheet>

    <PaySheet
      :open="paying"
      :due="due"
      :currency="currency"
      :modes="till.register.value?.payment_modes ?? []"
      :online="till.online.value"
      :busy="payBusy"
      :error="payError"
      @close="paying = false; payError = ''"
      @pay="pay"
    />

    <NSheet :open="!!receipt" :title="receipt?.mode === 'queued' ? t('Sale saved offline') : t('Sale complete')" @close="receipt = null">
      <div class="sell__receipt">
        <NIcon name="check" :size="40" class="sell__receipt-icon" />
        <p v-if="receipt?.change && Number(receipt.change)" class="sell__change">{{ t('Change') }} <strong class="num">{{ money(receipt.change, currency) }}</strong></p>
        <p v-if="receipt?.invoice" class="muted code">{{ receipt.invoice.name }}</p>
        <p v-if="receipt?.mode === 'queued'" class="muted">{{ t('It will be posted to ERPNext as soon as the till is back online. Do not close this device until it syncs.') }}</p>
      </div>
      <template #actions>
        <NButton v-if="receipt?.invoice" icon="receipt" @click="printReceipt">{{ t('Print receipt') }}</NButton>
        <NButton variant="primary" @click="receipt = null">{{ t('Next sale') }}</NButton>
      </template>
    </NSheet>

    <NSheet :open="held !== null" :title="t('Held sales')" @close="held = null">
      <p v-if="held && !held.length" class="muted">{{ t('No held sales on this register.') }}</p>
      <ul class="sell__list" role="list">
        <li v-for="h in held ?? []" :key="h.name">
          <button type="button" class="sell__list-item" @click="resume(h.name)">
            <span>{{ h.label || t('Held sale') }}</span>
            <span class="num">{{ money(h.total_preview, currency) }}</span>
          </button>
        </li>
      </ul>
    </NSheet>

    <NSheet :open="customerOpen" :title="t('Customer')" @close="customerOpen = false">
      <input v-model="customerQuery" class="sell__input" :placeholder="t('Name, phone or ID')" @input="searchCustomers" />
      <ul class="sell__list" role="list">
        <li><button type="button" class="sell__list-item" @click="till.cart.customer = null; customerOpen = false">{{ t('Walk-in customer') }}</button></li>
        <li v-for="c in customers" :key="c.name">
          <button type="button" class="sell__list-item" @click="till.cart.customer = c.name; customerOpen = false">
            <span>{{ c.customer_name }}</span><span class="muted code">{{ c.name }}</span>
          </button>
        </li>
      </ul>
    </NSheet>

    <NSheet :open="!!choice" :title="choice?.kind === 'variant' ? t('Choose a variant') : t('More than one product has this code')" @close="choice = null">
      <ul class="sell__list" role="list">
        <li v-for="c in choice?.candidates ?? []" :key="c">
          <button type="button" class="sell__list-item" @click="pick(c)">{{ till.catalog.value.find((i) => i.item_code === c)?.item_name ?? c }} <span class="muted code">{{ c }}</span></button>
        </li>
      </ul>
    </NSheet>
  </div>
</template>

<style>
.sell { flex: 1; min-block-size: 0; display: flex; position: relative; }
.sell__bar { display: none; }
.sell__scan-total { margin-block-start: var(--space-3); text-align: center; }
.sell__receipt { display: grid; justify-items: center; gap: var(--space-2); text-align: center; }
.sell__receipt-icon { color: var(--ok-fg); background: var(--ok-bg); border-radius: 50%; padding: 10px; box-sizing: content-box; }
.sell__change { font-size: var(--text-xl); }
.sell__change strong { font-size: var(--text-2xl); }
.sell__list { list-style: none; margin: var(--space-3) 0 0; padding: 0; display: grid; gap: var(--space-2); }
.sell__list-item { inline-size: 100%; display: flex; justify-content: space-between; gap: var(--space-3); min-block-size: var(--touch-lg); padding-inline: var(--space-4); border-radius: var(--radius-md); border: 1px solid var(--border-subtle); background: var(--surface-card); cursor: pointer; text-align: start; align-items: center; color: var(--text-strong); }
.sell__input { inline-size: 100%; min-block-size: var(--touch-lg); border-radius: var(--radius-md); border: 1px solid var(--border-strong); padding-inline: var(--space-3); background: var(--surface-card); color: var(--text-strong); }
@media (max-width: 1023px) {
  .sell { flex-direction: column; }
  .sell__tape { display: none; }
  .sell__bar {
    display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: var(--space-3);
    padding: var(--space-2) var(--space-3) calc(var(--space-2) + var(--safe-bottom)); background: var(--surface-card); border-block-start: 1px solid var(--border-subtle);
  }
  .sell__bar-basket { display: flex; align-items: center; gap: var(--space-2); min-block-size: var(--touch-lg); padding-inline: var(--space-3); border-radius: var(--radius-md); border: 1px solid var(--border-strong); background: var(--surface-card); color: var(--text-strong); cursor: pointer; min-inline-size: 0; text-align: start; }
  .sell__bar-sum { display: grid; line-height: 1.15; min-inline-size: 0; }
  .sell__bar-count { font-size: var(--text-xs); color: var(--text-muted); }
  .sell__bar-sum strong { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sell__bar-scan { inline-size: 68px; block-size: 68px; border-radius: 50%; border: 0; background: var(--brand-fill); color: var(--brand-on-fill); display: grid; place-items: center; margin-block-start: -24px; box-shadow: var(--shadow-overlay); cursor: pointer; }
}
</style>
