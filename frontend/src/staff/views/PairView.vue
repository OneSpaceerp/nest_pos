<script setup lang="ts">
// Two sides of phone-as-scanner:
//  - at the till: show a short code bound to this register, shift and the current cart
//  - on the phone: enter the code, then scan; each scan carries a sequence number so a resend is ignored
import { ref } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NScanner from '@shared/components/NScanner.vue'
import { toast } from '@shared/components/toast'
import { call } from '@shared/lib/api'
import { t } from '@shared/lib/i18n'
import { POS_API, useTill } from '../state'

const till = useTill()
const mode = ref<'choose' | 'desk' | 'phone'>('choose')
const pairing = ref<{ pairing: string; code: string; expires_in: number } | null>(null)
const joinCode = ref('')
const joined = ref<{ pairing: string; desktop_user: string } | null>(null)
const feedback = ref<{ tone: 'ok' | 'danger'; text: string } | null>(null)
let seq = Number(sessionStorage.getItem('nest_pos:pair_seq') ?? '0')
const busy = ref(false)

async function createPairing() {
  busy.value = true
  try {
    pairing.value = await call(POS_API('pairing.create'), { register_name: till.registerName.value, cart_id: till.cart.id })
    mode.value = 'desk'
  } catch (e) {
    toast((e as Error).message, 'danger')
  } finally {
    busy.value = false
  }
}

async function join() {
  busy.value = true
  try {
    joined.value = await call(POS_API('pairing.join'), { register_name: till.registerName.value, code: joinCode.value.trim().toUpperCase() })
  } catch (e) {
    toast((e as Error).message, 'danger')
  } finally {
    busy.value = false
  }
}

async function scan(code: string) {
  seq += 1
  sessionStorage.setItem('nest_pos:pair_seq', String(seq))
  try {
    const res = await call<{ result: { status: string; item_name?: string } }>(POS_API('pairing.scan'), { pairing_name: joined.value!.pairing, seq, code })
    feedback.value = res.result.status === 'ok' ? { tone: 'ok', text: `${res.result.item_name} → ${joined.value!.desktop_user}` } : { tone: 'danger', text: t('Not found') }
  } catch (e) {
    feedback.value = { tone: 'danger', text: (e as Error).message }
  }
  setTimeout(() => (feedback.value = null), 1500)
}

async function revoke(name: string) {
  await call(POS_API('pairing.revoke'), { pairing_name: name }).catch(() => undefined)
  pairing.value = null
  joined.value = null
  mode.value = 'choose'
}
</script>

<template>
  <div class="pair scroll">
    <section v-if="mode === 'choose'" class="pair__card">
      <h1>{{ t('Use a phone as a scanner') }}</h1>
      <p class="muted">{{ t('Scans from the phone go straight into one cart at one till. Nobody else’s sale can receive them.') }}</p>
      <div class="pair__choices">
        <NButton variant="primary" size="lg" icon="register" :busy="busy" @click="createPairing">{{ t('This is the till') }}</NButton>
        <NButton size="lg" icon="phone" @click="mode = 'phone'">{{ t('This is the phone') }}</NButton>
      </div>
    </section>

    <section v-else-if="mode === 'desk' && pairing" class="pair__card">
      <h1>{{ t('Pairing code') }}</h1>
      <p class="pair__code code" aria-live="polite">{{ pairing.code }}</p>
      <p class="muted">{{ t('On the phone, open Nest POS → Phone → This is the phone, and enter this code within {0} minutes.', Math.round(pairing.expires_in / 60)) }}</p>
      <NButton @click="revoke(pairing.pairing)">{{ t('Stop pairing') }}</NButton>
    </section>

    <section v-else-if="mode === 'phone' && !joined" class="pair__card">
      <h1>{{ t('Enter the code shown on the till') }}</h1>
      <form class="row" @submit.prevent="join">
        <input v-model="joinCode" class="pair__input code" maxlength="6" autocomplete="one-time-code" autocapitalize="characters" :aria-label="t('Pairing code')" />
        <NButton type="submit" variant="primary" :busy="busy" :disabled="joinCode.trim().length !== 6">{{ t('Pair') }}</NButton>
      </form>
    </section>

    <section v-else-if="joined" class="pair__phone">
      <p class="pair__target">{{ t('Scanning into the cart of {0}', joined.desktop_user) }}</p>
      <NScanner continuous :feedback="feedback" @code="scan" @close="revoke(joined.pairing)" />
    </section>
  </div>
</template>

<style>
.pair { flex: 1; padding: var(--space-5) var(--space-4); display: grid; place-items: start center; }
.pair__card { inline-size: min(560px, 100%); background: var(--surface-card); border-radius: var(--radius-lg); padding: var(--space-6); box-shadow: var(--shadow-raised); display: grid; gap: var(--space-4); }
.pair__choices { display: grid; gap: var(--space-3); }
.pair__code { font-size: clamp(2.5rem, 10vw, 4rem); font-weight: 700; letter-spacing: 0.18em; text-align: center; background: var(--brand-fill); color: var(--brand-on-fill); border-radius: var(--radius-lg); padding: var(--space-4); }
.pair__input { flex: 1; min-block-size: var(--touch-lg); font-size: var(--text-xl); letter-spacing: 0.2em; text-align: center; border-radius: var(--radius-md); border: 1px solid var(--border-strong); background: var(--surface-card); color: var(--text-strong); min-inline-size: 0; }
.pair__phone { inline-size: min(560px, 100%); display: grid; gap: var(--space-3); }
.pair__target { font-weight: 600; text-align: center; }
</style>
