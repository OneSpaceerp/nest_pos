<script setup lang="ts">
// Basket: build it, send it to the till, then show the hand-off code with live progress
// (waiting → with a cashier → at the till → paid).
import { computed } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NIcon from '@shared/components/NIcon.vue'
import NQty from '@shared/components/NQty.vue'
import NState from '@shared/components/NState.vue'
import { money, t } from '@shared/lib/i18n'
import { FINAL, cancelBasket, client, count, newBasket, sendBasket, sending, status, total, visit } from '../visit'

const emit = defineEmits<{ scan: [] }>()

const STEPS = ['Submitted', 'Claimed', 'Imported', 'Completed']
const STEP_LABEL: Record<string, string> = { Submitted: 'Sent', Claimed: 'With a cashier', Imported: 'At the till', Completed: 'Paid' }
const TEXT: Record<string, [string, string]> = {
  Submitted: ['Waiting for a cashier', 'Go to any till and show this code.'],
  Claimed: ['A cashier has your basket', 'They are checking your items now.'],
  Imported: ['Your basket is at the till', 'Pay at the till to finish.'],
  Completed: ['Paid — thank you', 'Your receipt is in your account.'],
  Cancelled: ['This basket was cancelled', 'Start a new basket if you still want to buy.'],
  Expired: ['This basket expired', 'Baskets wait for an hour. Start a new one.'],
}
const sent = computed(() => Boolean(visit.basket && status.value))
const stepIndex = computed(() => STEPS.indexOf(status.value?.status ?? ''))
const final = computed(() => FINAL.includes(status.value?.status ?? ''))
</script>

<template>
  <div class="bk">
    <template v-if="sent && status">
      <section class="bk__sent">
        <p class="bk__label">{{ t('Show this code at the till') }}</p>
        <p class="bk__code code" aria-live="polite">{{ status.handoff_code }}</p>
        <h1>{{ t(TEXT[status.status]?.[0] ?? status.status) }}</h1>
        <p class="muted">{{ status.status === 'Completed' && !client ? t('Your receipt comes from the till.') : t(TEXT[status.status]?.[1] ?? '') }}</p>
        <ol v-if="stepIndex >= 0" class="bk__steps" :aria-label="t('Progress')">
          <li v-for="(s, i) in STEPS" :key="s" :class="{ 'bk__step--done': i <= stepIndex, 'bk__step--now': i === stepIndex }">
            <span class="bk__dot"><NIcon v-if="i < stepIndex || s === 'Completed' && i === stepIndex" name="check" :size="14" /></span>
            <span>{{ t(STEP_LABEL[s]) }}</span>
          </li>
        </ol>
        <p class="bk__est num">{{ t('Estimated total') }} <strong>{{ money(status.total_preview, visit.currency) }}</strong></p>
        <p class="muted bk__small">{{ t('Prices are confirmed by the cashier. This is not a receipt.') }}</p>
        <NButton v-if="status.status === 'Submitted'" variant="ghost" @click="cancelBasket">{{ t('Cancel basket') }}</NButton>
        <NButton v-if="final" variant="primary" icon="plus" @click="newBasket">{{ t('Start a new basket') }}</NButton>
      </section>
    </template>

    <template v-else>
      <header class="bk__head">
        <h1>{{ t('Your basket') }}</h1>
        <span v-if="count" class="muted num">{{ t('{0} items', count) }}</span>
      </header>
      <NState v-if="!visit.lines.length" kind="empty" icon="basket" :title="t('Your basket is empty')" :detail="t('Scan a product to see its price and add it here.')" />
      <ul v-else class="bk__lines" role="list">
        <li v-for="(l, i) in visit.lines" :key="l.item_code" class="bk__line">
          <span class="bk__img"><img v-if="l.image" :src="l.image" alt="" loading="lazy" /><NIcon v-else name="image" :size="22" /></span>
          <span class="bk__info">
            <span class="bk__name">{{ l.item_name }}</span>
            <span class="muted num">{{ money(l.rate, visit.currency) }}</span>
          </span>
          <span class="bk__right">
            <strong class="num">{{ money(l.rate * l.qty, visit.currency) }}</strong>
            <NQty :model-value="l.qty" :min="0" :label="t('Quantity of {0}', l.item_name)" @update:model-value="(v: number) => (v ? (l.qty = v) : visit.lines.splice(i, 1))" />
          </span>
        </li>
      </ul>
      <button type="button" class="bk__more" @click="emit('scan')"><NIcon name="scan" />{{ t('Scan another product') }}</button>

      <section v-if="visit.lines.length" class="bk__checkout">
        <div class="bk__total"><span>{{ t('Estimated total') }}</span><strong class="num">{{ money(total, visit.currency) }}</strong></div>
        <p v-if="client" class="bk__who"><NIcon name="user" :size="16" />{{ t('The cashier will see it’s you, {0}.', client.full_name.split(' ')[0]) }}</p>
        <NButton variant="primary" size="lg" block icon="send" :busy="sending" :disabled="!visit.token" @click="sendBasket">{{ t('Send basket to cashier') }}</NButton>
        <p class="muted bk__small">{{ t('You pay at the till. Prices are confirmed by the cashier.') }}</p>
      </section>
    </template>
  </div>
</template>

<style>
.bk { display: grid; gap: var(--space-4); }
.bk__head { display: flex; align-items: baseline; justify-content: space-between; }
.bk__head h1 { font-size: var(--text-2xl); color: var(--text-strong); }
.bk__lines { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.bk__line { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); background: var(--surface-card); border-radius: var(--radius-lg); border: 1px solid var(--border-subtle); }
.bk__img { inline-size: 56px; block-size: 56px; flex: none; display: grid; place-items: center; border-radius: var(--radius-md); background: var(--surface-sunken); overflow: hidden; color: var(--text-muted); }
.bk__img img { inline-size: 100%; block-size: 100%; object-fit: cover; }
.bk__info { flex: 1; min-inline-size: 0; display: grid; gap: 2px; }
.bk__name { font-weight: 600; color: var(--text-strong); overflow-wrap: anywhere; }
.bk__right { display: grid; justify-items: end; gap: var(--space-2); }
.bk__more { display: flex; align-items: center; justify-content: center; gap: var(--space-2); min-block-size: var(--touch-lg); border: 2px dashed var(--border-strong); border-radius: var(--radius-lg); background: transparent; color: var(--text-strong); font: inherit; font-weight: 600; cursor: pointer; }
.bk__checkout { display: grid; gap: var(--space-3); padding: var(--space-4); border-radius: var(--radius-lg); background: var(--surface-card); box-shadow: var(--shadow-raised); }
.bk__total { display: flex; justify-content: space-between; align-items: baseline; font-weight: 600; }
.bk__total strong { font-size: var(--text-2xl); color: var(--text-strong); }
.bk__who { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); color: var(--ok-fg); font-weight: 600; }
.bk__small { font-size: var(--text-sm); text-align: center; }
.bk__sent { display: grid; justify-items: center; text-align: center; gap: var(--space-3); padding-block-start: var(--space-3); }
.bk__sent h1 { font-size: var(--text-xl); color: var(--text-strong); }
.bk__label { font-weight: 600; }
.bk__code { font-size: clamp(3rem, 15vw, 4.75rem); font-weight: 700; letter-spacing: 0.16em; padding: var(--space-3) var(--space-5); border-radius: 22px; background: var(--brand-fill); color: var(--brand-on-fill); box-shadow: var(--shadow-overlay); }
.bk__steps { list-style: none; margin: var(--space-2) 0; padding: 0; display: grid; grid-template-columns: repeat(4, 1fr); inline-size: 100%; }
.bk__steps li { position: relative; display: grid; justify-items: center; gap: 6px; font-size: var(--text-xs); color: var(--text-muted); font-weight: 600; }
.bk__steps li + li::before { content: ''; position: absolute; inset-block-start: 11px; inset-inline-end: 50%; inline-size: 100%; block-size: 3px; background: var(--border-subtle); z-index: 0; }
.bk__steps li.bk__step--done + li.bk__step--done::before { background: var(--text-strong); }
.bk__dot { position: relative; z-index: 1; inline-size: 24px; block-size: 24px; border-radius: 50%; display: grid; place-items: center; background: var(--surface-sunken); border: 3px solid var(--surface-page); box-sizing: content-box; }
.bk__step--done { color: var(--text-strong) !important; }
.bk__step--done .bk__dot { background: var(--text-strong); color: var(--brand-fill); }
.bk__step--now .bk__dot { background: var(--brand-fill); color: var(--brand-on-fill); box-shadow: 0 0 0 3px var(--text-strong); }
.bk__est { font-size: var(--text-md); }
</style>
