<script setup lang="ts">
// Recent sales on this shift, reprint, and full/partial returns against the original rows.
import { computed, onMounted, ref } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NQty from '@shared/components/NQty.vue'
import NSheet from '@shared/components/NSheet.vue'
import NState from '@shared/components/NState.vue'
import NStatus from '@shared/components/NStatus.vue'
import { toast } from '@shared/components/toast'
import { call, newKey } from '@shared/lib/api'
import { money, t } from '@shared/lib/i18n'
import { receiptUrl } from '@shared/till/till'
import { useTill } from '../state'

interface Sale { name: string; customer_name: string; rounded_total: number; grand_total: number; posting_time: string; is_return: number; currency: string }
interface Row { row_id: string; item_name: string; qty: number; returned_qty: string; net_unit: number; serial_nos: string[]; returned_serials: string[] }

const till = useTill()
const sales = ref<Sale[] | null>(null)
const query = ref('')
const error = ref('')
const ret = ref<{ invoice: string; rows: Row[] } | null>(null)
const picks = ref<Record<string, number>>({})
const serialPicks = ref<Record<string, string[]>>({})
const reason = ref('')
const refundMode = ref('')
const busy = ref(false)
const invoiceDt = computed(() => (till.register.value?.invoice_mode === 'Consolidated' ? 'POS Invoice' : 'Sales Invoice'))
const refund = computed(() => (ret.value?.rows ?? []).reduce((a, r) => a + (picks.value[r.row_id] || 0) * r.net_unit, 0))

async function load() {
  try {
    sales.value = await call<Sale[]>(till.api('recent_sales'), { register_name: till.registerName.value, query: query.value }, { method: 'GET' })
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}
onMounted(load)

async function startReturn(s: Sale) {
  const data = await call<{ invoice: string; rows: Row[] }>(till.api('returnable'), { invoice_doctype: invoiceDt.value, invoice: s.name }, { method: 'GET' })
  ret.value = data
  picks.value = {}
  serialPicks.value = {}
  reason.value = till.boot.value?.return_reasons[0]?.reason ?? ''
  refundMode.value = till.register.value?.payment_modes.find((m) => m.type === 'Cash')?.mode_of_payment ?? till.register.value?.payment_modes[0]?.mode_of_payment ?? ''
}

async function submitReturn() {
  busy.value = true
  try {
    const rows = Object.fromEntries(
      Object.entries(picks.value).filter(([, q]) => q > 0).map(([row, qty]) => [row, { qty, serial_nos: serialPicks.value[row] ?? [] }]),
    )
    const res = await call<{ invoice: { name: string } }>(till.api('create_return'), {
      register_name: till.registerName.value,
      payload: { invoice_doctype: invoiceDt.value, invoice: ret.value!.invoice, rows, reason: reason.value, refund_mode: refundMode.value, session: till.register.value?.session },
      request_key: newKey('ret-'),
    })
    toast(t('Return {0} posted', res.invoice.name))
    ret.value = null
    await load()
  } catch (e) {
    toast((e as Error).message, 'danger')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="sales scroll">
    <header class="sales__head">
      <h1>{{ t('Sales and returns') }}</h1>
      <form class="row" role="search" @submit.prevent="load">
        <input v-model="query" class="sales__q" type="search" :placeholder="t('Invoice or customer')" :aria-label="t('Invoice or customer')" />
        <NButton type="submit" icon="search">{{ t('Find') }}</NButton>
      </form>
    </header>
    <NState v-if="error" kind="error" :title="t('Sales could not be loaded')" :detail="error" :retry="load" />
    <NState v-else-if="!sales" kind="loading" :title="t('Loading sales')" />
    <NState v-else-if="!sales.length" kind="empty" icon="receipt" :title="t('No sales on this shift yet')" />
    <table v-else class="sales__table">
      <thead><tr><th scope="col">{{ t('Invoice') }}</th><th scope="col">{{ t('Customer') }}</th><th scope="col">{{ t('Time') }}</th><th scope="col" class="num">{{ t('Total') }}</th><th scope="col"><span class="sr-only">{{ t('Actions') }}</span></th></tr></thead>
      <tbody>
        <tr v-for="s in sales" :key="s.name">
          <td class="code">{{ s.name }} <NStatus v-if="s.is_return" tone="warn" :label="t('Return')" /></td>
          <td>{{ s.customer_name }}</td>
          <td class="num">{{ s.posting_time?.slice(0, 5) }}</td>
          <td class="num">{{ money(s.rounded_total || s.grand_total, s.currency) }}</td>
          <td class="sales__actions">
            <a class="sales__link" :href="receiptUrl(till.register.value, invoiceDt, s.name)" target="_blank" rel="noopener">{{ t('Reprint') }}</a>
            <NButton v-if="!s.is_return" size="sm" icon="undo" @click="startReturn(s)">{{ t('Return') }}</NButton>
          </td>
        </tr>
      </tbody>
    </table>

    <NSheet :open="!!ret" :title="t('Return from {0}', ret?.invoice ?? '')" wide @close="ret = null">
      <ul class="sales__ret" role="list">
        <li v-for="r in ret?.rows ?? []" :key="r.row_id">
          <span>{{ r.item_name }}<br /><span class="muted">{{ t('{0} sold, {1} already returned', r.qty, r.returned_qty) }}</span></span>
          <template v-if="r.serial_nos.length">
            <span class="sales__serials">
              <label v-for="sn in r.serial_nos.filter((x) => !r.returned_serials.includes(x))" :key="sn" class="row code">
                <input v-model="serialPicks[r.row_id]" type="checkbox" :value="sn" @change="picks[r.row_id] = (serialPicks[r.row_id] ?? []).length" /> {{ sn }}
              </label>
            </span>
          </template>
          <NQty v-else :model-value="picks[r.row_id] ?? 0" :max="r.qty - Number(r.returned_qty)" :label="t('Return quantity of {0}', r.item_name)" @update:model-value="(v: number) => (picks[r.row_id] = v)" />
        </li>
      </ul>
      <div class="sales__opts">
        <label class="stack"><span>{{ t('Reason') }}</span>
          <select v-model="reason" class="sales__q"><option v-for="rr in till.boot.value?.return_reasons ?? []" :key="rr.reason" :value="rr.reason">{{ rr.reason }}</option></select>
        </label>
        <label class="stack"><span>{{ t('Refund to') }}</span>
          <select v-model="refundMode" class="sales__q"><option v-for="m in till.register.value?.payment_modes ?? []" :key="m.mode_of_payment" :value="m.mode_of_payment">{{ m.mode_of_payment }}</option></select>
        </label>
      </div>
      <p class="sales__refund">{{ t('Refund (estimate)') }} <strong class="num">{{ money(refund, till.register.value?.currency) }}</strong></p>
      <template #actions>
        <NButton @click="ret = null">{{ t('Cancel') }}</NButton>
        <NButton variant="primary" :busy="busy" :disabled="!refund || !till.online.value" @click="submitReturn">{{ t('Post return') }}</NButton>
      </template>
    </NSheet>
  </div>
</template>

<style>
.sales { flex: 1; padding: var(--space-5) var(--space-4); display: grid; gap: var(--space-4); align-content: start; max-inline-size: 1100px; margin-inline: auto; inline-size: 100%; }
.sales__head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.sales__q { min-block-size: var(--touch); border-radius: var(--radius-md); border: 1px solid var(--border-strong); padding-inline: var(--space-3); background: var(--surface-card); color: var(--text-strong); min-inline-size: 0; }
.sales__table { inline-size: 100%; border-collapse: collapse; background: var(--surface-card); border-radius: var(--radius-md); overflow: hidden; box-shadow: var(--shadow-raised); }
.sales__table th, .sales__table td { padding: var(--space-3); text-align: start; border-block-end: 1px solid var(--border-subtle); vertical-align: middle; }
.sales__table td.num, .sales__table th.num { text-align: end; }
.sales__actions { display: flex; gap: var(--space-2); justify-content: flex-end; align-items: center; }
.sales__link { color: var(--text-strong); font-weight: 600; min-block-size: 36px; display: inline-flex; align-items: center; padding-inline: var(--space-2); }
.sales__ret { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-3); }
.sales__ret li { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); padding-block: var(--space-2); border-block-end: 1px dashed var(--border-subtle); }
.sales__serials { display: grid; gap: var(--space-1); }
.sales__opts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); margin-block: var(--space-4); }
.sales__refund { font-size: var(--text-lg); text-align: end; }
@media (max-width: 720px) {
  .sales__table thead { display: none; }
  .sales__table tr { display: grid; grid-template-columns: 1fr auto; padding: var(--space-2); border-block-end: 1px solid var(--border-subtle); }
  .sales__table td { border: 0; padding: var(--space-1) var(--space-2); }
  .sales__opts { grid-template-columns: 1fr; }
}
</style>
