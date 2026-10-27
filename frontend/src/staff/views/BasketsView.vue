<script setup lang="ts">
// Client basket inbox: realtime with a polling safety net. Claim is atomic on the server; import is
// exactly-once per basket and flags any price that changed since the shopper saw it.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import NButton from '@shared/components/NButton.vue'
import NSheet from '@shared/components/NSheet.vue'
import NState from '@shared/components/NState.vue'
import NStatus from '@shared/components/NStatus.vue'
import { toast } from '@shared/components/toast'
import { call } from '@shared/lib/api'
import { minutesAgo, money, t } from '@shared/lib/i18n'
import { on, poll } from '@shared/lib/realtime'
import { POS_API, useTill } from '../state'

interface Row { name: string; handoff_code: string; status: string; claimed_by: string | null; total_preview: number; creation: string }
interface Imported { basket: string; handoff_code: string; note: string; lines: { item_code: string; item_name: string; qty: number; rate_preview: number; rate_now: number | null; price_changed: boolean; available: boolean }[] }

const till = useTill()
const router = useRouter()
const rows = ref<Row[] | null>(null)
const error = ref('')
const busy = ref<string | null>(null)
const review = ref<Imported | null>(null)
const currency = computed(() => till.register.value?.currency ?? 'USD')

async function load() {
  try {
    rows.value = await call<Row[]>(POS_API('baskets.inbox'), { register_name: till.registerName.value }, { method: 'GET' })
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function claimAndImport(row: Row) {
  if (till.cart.lines.length) return toast(t('Finish or hold the current sale before importing a basket.'), 'warn')
  busy.value = row.name
  try {
    await call(POS_API('baskets.claim'), { basket: row.name })
    review.value = await call<Imported>(POS_API('baskets.import_basket'), { basket: row.name, cart_id: till.cart.id })
  } catch (e) {
    toast((e as Error).message, 'danger')
    await load()
  } finally {
    busy.value = null
  }
}

function accept() {
  const r = review.value!
  for (const l of r.lines.filter((x) => x.available)) {
    const item = till.catalog.value.find((i) => i.item_code === l.item_code)
    till.addItem({ item_code: l.item_code, item_name: l.item_name, rate: l.rate_now ?? item?.rate ?? null, item_group: item?.item_group }, l.qty)
  }
  till.cart.basket = r.basket
  review.value = null
  void router.push('/sell')
}

async function release(name: string) {
  await call(POS_API('baskets.release'), { basket: name }).catch((e) => toast(e.message, 'danger'))
  review.value = null
  await load()
}

let stopPoll: () => void = () => undefined
let off: (() => void) | undefined
onMounted(() => {
  void load()
  off = on('nest_pos:basket', () => void load())
  stopPoll = poll(load, 30000, 5000)
})
onBeforeUnmount(() => {
  off?.()
  stopPoll()
})
const age = (c: string) => (Date.now() - new Date(c.replace(' ', 'T')).getTime()) / 60000
</script>

<template>
  <div class="bsk scroll">
    <header class="bsk__head">
      <h1>{{ t('Client baskets') }}</h1>
      <p class="muted">{{ t('Baskets shoppers sent from their phones. A basket is not paid until you complete the sale.') }}</p>
    </header>
    <NState v-if="error" kind="error" :title="t('Baskets could not be loaded')" :detail="error" :retry="load" />
    <NState v-else-if="!rows" kind="loading" :title="t('Loading baskets')" />
    <NState v-else-if="!rows.length" kind="empty" icon="basket" :title="t('No baskets waiting')" :detail="t('New baskets appear here as soon as a shopper sends one.')" />
    <ul v-else class="bsk__list" role="list">
      <li v-for="r in rows" :key="r.name" class="bsk__row">
        <span class="bsk__code code">{{ r.handoff_code }}</span>
        <span class="bsk__meta">
          <NStatus :tone="r.status === 'Submitted' ? 'brand' : 'info'" :label="r.status === 'Submitted' ? t('Waiting') : t('With {0}', r.claimed_by ?? '')" />
          <span class="muted">{{ minutesAgo(age(r.creation)) }}</span>
        </span>
        <span class="bsk__total num">{{ money(r.total_preview, currency) }}</span>
        <NButton v-if="r.status === 'Submitted' || r.claimed_by === till.boot.value?.user" variant="primary" :busy="busy === r.name" @click="claimAndImport(r)">{{ t('Claim') }}</NButton>
      </li>
    </ul>

    <NSheet :open="!!review" :title="t('Basket {0}', review?.handoff_code ?? '')" @close="review = null">
      <p v-if="review?.note" class="bsk__note">“{{ review.note }}”</p>
      <ul class="bsk__lines" role="list">
        <li v-for="l in review?.lines ?? []" :key="l.item_code" :class="{ 'bsk__line--off': !l.available }">
          <span>{{ l.item_name }} <span class="num muted">× {{ l.qty }}</span></span>
          <span class="num">
            <template v-if="!l.available">{{ t('Unavailable') }}</template>
            <template v-else-if="l.price_changed"><s>{{ money(l.rate_preview, currency) }}</s> {{ money(l.rate_now ?? 0, currency) }}</template>
            <template v-else>{{ money(l.rate_now ?? 0, currency) }}</template>
          </span>
        </li>
      </ul>
      <p v-if="review?.lines.some((l) => l.price_changed || !l.available)" class="bsk__warn" role="status">{{ t('Some prices or items changed since the shopper saw them. Tell them before taking payment.') }}</p>
      <template #actions>
        <NButton @click="release(review!.basket)">{{ t('Release') }}</NButton>
        <NButton variant="primary" @click="accept">{{ t('Import into sale') }}</NButton>
      </template>
    </NSheet>
  </div>
</template>

<style>
.bsk { flex: 1; padding: var(--space-5) var(--space-4); display: grid; gap: var(--space-4); align-content: start; max-inline-size: 960px; margin-inline: auto; inline-size: 100%; }
.bsk__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.bsk__row { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: var(--space-4); background: var(--surface-card); border-radius: var(--radius-md); padding: var(--space-3) var(--space-4); box-shadow: var(--shadow-raised); }
.bsk__code { font-size: var(--text-xl); font-weight: 700; letter-spacing: 0.08em; color: var(--text-strong); }
.bsk__meta { display: flex; gap: var(--space-3); align-items: center; flex-wrap: wrap; }
.bsk__total { font-weight: 700; color: var(--text-strong); }
.bsk__lines { list-style: none; padding: 0; margin: 0; display: grid; gap: var(--space-2); }
.bsk__lines li { display: flex; justify-content: space-between; gap: var(--space-3); padding-block: var(--space-2); border-block-end: 1px dashed var(--border-subtle); }
.bsk__line--off { color: var(--text-muted); text-decoration: line-through; }
.bsk__warn { background: var(--warn-bg); color: var(--warn-fg); padding: var(--space-3); border-radius: var(--radius-md); margin-block-start: var(--space-3); }
.bsk__note { font-style: italic; margin-block-end: var(--space-3); }
@media (max-width: 640px) { .bsk__row { grid-template-columns: auto 1fr; } .bsk__row > :last-child { grid-column: 1 / -1; } }
</style>
