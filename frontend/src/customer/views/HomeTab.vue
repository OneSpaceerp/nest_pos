<script setup lang="ts">
// Home: who you are, where you are, one big "scan" action, your basket's live state, and the prices
// you've already checked so you can add them without scanning twice.
import { computed } from 'vue'
import NIcon from '@shared/components/NIcon.vue'
import { toast } from '@shared/components/toast'
import { money, t } from '@shared/lib/i18n'
import { FINAL, addToBasket, client, count, status, total, visit, type PriceView } from '../visit'

const emit = defineEmits<{ scan: []; product: [PriceView]; go: ['home' | 'basket' | 'account'] }>()

const greeting = computed(() => {
  const h = new Date().getHours()
  const part = h < 12 ? t('Good morning') : h < 18 ? t('Good afternoon') : t('Good evening')
  const first = client.value?.full_name.split(' ')[0]
  return first ? t('{0}, {1}', part, first) : part
})
const liveBasket = computed(() => (visit.basket && status.value && !FINAL.includes(status.value.status) ? status.value : null))

function quickAdd(p: PriceView) {
  if (addToBasket(p, 1)) toast(t('{0} added to your basket', p.item_name))
}
</script>

<template>
  <div class="home">
    <section class="home__hello">
      <h1>{{ greeting }}</h1>
      <p class="muted">{{ visit.outlet ? t('Shopping at {0}', visit.outlet) : t('Choose your store to start') }}</p>
    </section>

    <button type="button" class="home__hero" @click="emit('scan')">
      <span class="home__hero-icon"><NIcon name="scan" :size="34" /></span>
      <span class="home__hero-text">
        <strong>{{ t('Scan a product') }}</strong>
        <span>{{ t('See its price before you buy, then add it to your basket.') }}</span>
      </span>
      <NIcon name="chevron" class="home__hero-go" />
    </button>

    <button v-if="liveBasket" type="button" class="home__live" @click="emit('go', 'basket')">
      <span class="home__live-code code">{{ liveBasket.handoff_code }}</span>
      <span class="home__live-text">
        <strong>{{ liveBasket.status === 'Submitted' ? t('Your basket is waiting for a cashier') : liveBasket.status === 'Claimed' ? t('A cashier has your basket') : t('Your basket is at the till') }}</strong>
        <span class="muted">{{ t('Show this code at the till') }}</span>
      </span>
    </button>
    <button v-else-if="count" type="button" class="home__live home__live--draft" @click="emit('go', 'basket')">
      <span class="home__live-count num">{{ count }}</span>
      <span class="home__live-text"><strong>{{ t('Your basket') }}</strong><span class="muted num">{{ money(total, visit.currency) }} · {{ t('Send it to a cashier when you’re ready') }}</span></span>
      <NIcon name="chevron" />
    </button>

    <section v-if="visit.recent.length" class="home__block">
      <h2>{{ t('Prices you checked') }}</h2>
      <ul class="home__recent" role="list">
        <li v-for="p in visit.recent" :key="p.item_code" class="home__rcard">
          <button type="button" class="home__rcard-open" @click="emit('product', p)">
            <span class="home__rimg"><img v-if="p.image" :src="p.image" alt="" loading="lazy" /><NIcon v-else name="image" :size="24" /></span>
            <span class="home__rname">{{ p.item_name }}</span>
            <span class="home__rprice num">{{ money(p.rate, p.currency) }}</span>
          </button>
          <button type="button" class="home__radd" :aria-label="t('Add {0} to your basket', p.item_name)" :disabled="p.availability === 'out'" @click="quickAdd(p)"><NIcon name="plus" :size="18" /></button>
        </li>
      </ul>
    </section>

    <section v-if="!client" class="home__join">
      <div>
        <strong>{{ t('Make it yours') }}</strong>
        <p>{{ t('Create a free account to keep your receipts and let the cashier know it’s you.') }}</p>
      </div>
      <button type="button" class="home__join-btn" @click="emit('go', 'account')">{{ t('Create account') }}</button>
    </section>
    <button v-else type="button" class="home__link" @click="emit('go', 'account')">
      <NIcon name="receipt" /><span>{{ t('My purchases and receipts') }}</span><NIcon name="chevron" />
    </button>

    <ol class="home__how">
      <li><span class="num">1</span>{{ t('Scan products as you shop') }}</li>
      <li><span class="num">2</span>{{ t('Send your basket to the till') }}</li>
      <li><span class="num">3</span>{{ t('Show your code and pay') }}</li>
    </ol>
  </div>
</template>

<style>
.home { display: grid; gap: var(--space-4); }
.home__hello h1 { font-size: var(--text-2xl); line-height: var(--leading-tight); color: var(--text-strong); }
.home__hero { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-5); border: 0; border-radius: 22px; background: var(--action-primary-bg); color: var(--action-primary-fg); text-align: start; cursor: pointer; font: inherit; box-shadow: var(--shadow-overlay); }
.home__hero-icon { inline-size: 64px; block-size: 64px; border-radius: 18px; background: var(--brand-fill); color: var(--brand-on-fill); display: grid; place-items: center; flex: none; }
.home__hero-text { flex: 1; display: grid; gap: 4px; }
.home__hero-text strong { font-size: var(--text-xl); }
.home__hero-text span { opacity: 0.8; font-size: var(--text-sm); }
.home__hero-go { opacity: 0.7; }
.home__live { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 2px solid var(--nest-yellow-500); border-radius: var(--radius-lg); background: var(--surface-card); text-align: start; cursor: pointer; font: inherit; color: var(--text-body); }
.home__live--draft { border-color: var(--border-subtle); }
.home__live-code { font-size: var(--text-xl); font-weight: 700; letter-spacing: 0.12em; padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--brand-fill); color: var(--brand-on-fill); }
.home__live-count { inline-size: 44px; block-size: 44px; display: grid; place-items: center; border-radius: 50%; background: var(--brand-fill); color: var(--brand-on-fill); font-weight: 700; flex: none; }
.home__live-text { flex: 1; min-inline-size: 0; display: grid; gap: 2px; }
.home__live-text strong { color: var(--text-strong); }
.home__block h2 { font-size: var(--text-md); margin-block-end: var(--space-2); color: var(--text-strong); }
.home__recent { list-style: none; margin: 0 calc(-1 * var(--space-4)); padding: 2px var(--space-4) var(--space-2); display: flex; gap: var(--space-3); overflow-x: auto; scroll-snap-type: x mandatory; }
.home__rcard { position: relative; flex: none; inline-size: 148px; scroll-snap-align: start; }
.home__rcard-open { inline-size: 100%; display: grid; gap: 4px; padding: var(--space-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); background: var(--surface-card); text-align: start; cursor: pointer; font: inherit; color: var(--text-body); }
.home__rimg { aspect-ratio: 1; display: grid; place-items: center; background: var(--surface-sunken); border-radius: var(--radius-md); overflow: hidden; color: var(--text-muted); }
.home__rimg img { inline-size: 100%; block-size: 100%; object-fit: cover; }
.home__rname { font-weight: 600; font-size: var(--text-sm); color: var(--text-strong); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-block-size: 2.6em; }
.home__rprice { font-weight: 700; color: var(--text-strong); }
.home__radd { position: absolute; inset-block-end: var(--space-2); inset-inline-end: var(--space-2); inline-size: 40px; block-size: 40px; border-radius: 50%; border: 0; background: var(--brand-fill); color: var(--brand-on-fill); display: grid; place-items: center; cursor: pointer; box-shadow: var(--shadow-raised); }
.home__radd:disabled { opacity: 0.4; cursor: not-allowed; }
.home__join { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-radius: var(--radius-lg); background: var(--brand-fill); color: var(--brand-on-fill); }
.home__join div { flex: 1; display: grid; gap: 2px; }
.home__join p { font-size: var(--text-sm); }
.home__join-btn { flex: none; min-block-size: var(--touch); padding-inline: var(--space-4); border: 0; border-radius: var(--radius-pill); background: var(--nest-ink-900); color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.home__link { display: flex; align-items: center; gap: var(--space-3); min-block-size: var(--touch-lg); padding-inline: var(--space-4); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); background: var(--surface-card); color: var(--text-strong); font: inherit; font-weight: 600; cursor: pointer; text-align: start; }
.home__link span { flex: 1; }
.home__how { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
.home__how li { display: grid; justify-items: center; gap: var(--space-2); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
.home__how span { inline-size: 28px; block-size: 28px; display: grid; place-items: center; border-radius: 50%; background: var(--surface-sunken); color: var(--text-strong); font-weight: 700; }
</style>
