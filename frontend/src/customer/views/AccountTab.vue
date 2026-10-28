<script setup lang="ts">
// Account: sign in or create a shopper account (Frappe login underneath), then profile, purchases with
// receipts, and sign out. A staff account opened here is pointed to the staff app instead.
import { computed, onMounted, ref, watch } from 'vue'
import NButton from '@shared/components/NButton.vue'
import NIcon from '@shared/components/NIcon.vue'
import NSheet from '@shared/components/NSheet.vue'
import NState from '@shared/components/NState.vue'
import { toast } from '@shared/components/toast'
import { call } from '@shared/lib/api'
import { SignInError, signIn } from '@shared/lib/auth'
import { money, t } from '@shared/lib/i18n'
import { ACCOUNT_API, accountMode, client, signedInElsewhere, type Client } from '../visit'

const emit = defineEmits<{ go: ['home' | 'basket' | 'account'] }>()

// ------------------------------------------------------------------ signed out
const mode = accountMode
const form = ref({ full_name: '', email: '', mobile: '', password: '', otp: '' })
const showPwd = ref(false)
const busy = ref(false)
const error = ref('')
const otpStep = ref<{ tmpId: string; prompt: string } | null>(null)

const strength = computed(() => {
  const p = form.value.password
  let s = 0
  if (p.length >= 8) s++
  if (p.length >= 12) s++
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++
  if (/\d/.test(p) && /[^\w]/.test(p)) s++
  return p ? Math.max(1, s) : 0
})
const STRENGTH = ['', 'Weak', 'Fair', 'Good', 'Strong']
watch(mode, () => (error.value = ''))

async function submit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    if (mode.value === 'signup') {
      await call<Client>(ACCOUNT_API('signup'), { full_name: form.value.full_name, email: form.value.email, mobile: form.value.mobile, password: form.value.password })
    } else {
      const res = otpStep.value
        ? await signIn({ otp: form.value.otp, tmpId: otpStep.value.tmpId })
        : await signIn({ usr: form.value.email.trim(), pwd: form.value.password })
      if (res.status === 'otp') {
        otpStep.value = { tmpId: res.tmpId, prompt: res.prompt }
        busy.value = false
        return
      }
    }
    // the shopper shell is rendered per session (account, CSRF token): load it again, back on this tab
    location.hash = '#account'
    location.reload()
  } catch (e) {
    busy.value = false
    error.value = e instanceof SignInError ? t(e.message) : (e as Error).message
    form.value.password = ''
  }
}

// ------------------------------------------------------------------ signed in
interface Purchase { doctype: string; name: string; posting_date: string; posting_time: string; total: number; currency: string; is_return: number; total_qty: number }
interface Receipt { doctype: string; name: string; posting_date: string; posting_time: string; outlet: string; currency: string; is_return: number; items: { item_name: string; qty: number; uom: string; rate: number; amount: number }[]; net_total: number; discount: number; taxes: { description: string; amount: number }[]; total: number; payments: { mode: string; amount: number }[]; change: number }

const purchases = ref<Purchase[] | null>(null)
const purchasesError = ref('')
const receipt = ref<Receipt | null>(null)
const editing = ref<{ full_name: string; mobile: string } | null>(null)
const saving = ref(false)

async function loadPurchases() {
  purchasesError.value = ''
  try {
    purchases.value = await call<Purchase[]>(ACCOUNT_API('purchases'), { limit: 30 }, { method: 'GET' })
  } catch (e) {
    purchasesError.value = (e as Error).message
  }
}
async function openReceipt(p: Purchase) {
  try {
    receipt.value = await call<Receipt>(ACCOUNT_API('purchase'), { doctype: p.doctype, name: p.name }, { method: 'GET' })
  } catch (e) {
    toast((e as Error).message, 'danger')
  }
}
async function saveProfile() {
  if (!editing.value) return
  saving.value = true
  try {
    client.value = await call<Client>(ACCOUNT_API('update_profile'), editing.value)
    editing.value = null
    toast(t('Profile saved'))
  } catch (e) {
    toast((e as Error).message, 'danger')
  } finally {
    saving.value = false
  }
}
async function signOut() {
  await call('logout', {}, { method: 'POST' }).catch(() => undefined)
  // back to the Nest POS sign-in page, which also offers "Shopper sign in" and "Create account"
  location.replace('/nest-pos/')
}
const initials = computed(() => (client.value?.full_name ?? '').split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase())
const fmtDate = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
onMounted(() => client.value && void loadPurchases())
</script>

<template>
  <div class="acc">
    <!-- a staff or Desk account is signed in on this browser -->
    <template v-if="signedInElsewhere">
      <NState kind="empty" icon="user" :title="t('You are signed in with a staff account')" :detail="t('Shopper accounts are separate. Sign out to create or use one.')" />
      <NButton variant="primary" block @click="signOut">{{ t('Sign out') }}</NButton>
      <a class="acc__link" href="/nest-pos/">{{ t('Open the staff app') }}</a>
    </template>

    <!-- signed out: sign in or create an account -->
    <template v-else-if="!client">
      <header class="acc__intro">
        <h1>{{ mode === 'signup' ? t('Create your account') : t('Welcome back') }}</h1>
        <p class="muted">{{ t('Keep your receipts in one place and let the cashier know it’s you.') }}</p>
      </header>
      <div class="acc__switch" role="tablist">
        <button type="button" role="tab" :aria-selected="mode === 'signup'" @click="mode = 'signup'; otpStep = null">{{ t('Create account') }}</button>
        <button type="button" role="tab" :aria-selected="mode === 'signin'" @click="mode = 'signin'">{{ t('Sign in') }}</button>
      </div>
      <form class="acc__form" novalidate @submit.prevent="submit">
        <template v-if="otpStep">
          <label class="acc__field">{{ t('Verification code') }}
            <input v-model="form.otp" class="acc__input acc__otp" inputmode="numeric" autocomplete="one-time-code" maxlength="10" dir="ltr" />
          </label>
          <p class="muted">{{ otpStep.prompt || t('Enter the code from your authenticator app.') }}</p>
        </template>
        <template v-else>
          <label v-if="mode === 'signup'" class="acc__field">{{ t('Full name') }}
            <input v-model="form.full_name" class="acc__input" autocomplete="name" maxlength="140" />
          </label>
          <label class="acc__field">{{ t('Email') }}
            <input v-model="form.email" class="acc__input" type="email" inputmode="email" autocomplete="email" autocapitalize="none" spellcheck="false" maxlength="140" dir="ltr" />
          </label>
          <label v-if="mode === 'signup'" class="acc__field"><span>{{ t('Mobile number') }} <small class="muted">({{ t('optional') }})</small></span>
            <input v-model="form.mobile" class="acc__input" type="tel" inputmode="tel" autocomplete="tel" maxlength="20" dir="ltr" />
          </label>
          <div class="acc__field">
            <label for="acc-pwd">{{ t('Password') }}</label>
            <span class="acc__pwd" dir="ltr">
              <input id="acc-pwd" v-model="form.password" class="acc__input" :type="showPwd ? 'text' : 'password'" :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'" />
              <button type="button" class="acc__reveal" :aria-pressed="showPwd" :aria-label="showPwd ? t('Hide password') : t('Show password')" @click="showPwd = !showPwd">{{ showPwd ? t('Hide') : t('Show') }}</button>
            </span>
            <span v-if="mode === 'signup' && form.password" :class="['acc__meter', `acc__meter--${strength}`]"><i /><i /><i /><i /><b>{{ t(STRENGTH[strength]) }}</b></span>
            <span v-else-if="mode === 'signup'" class="muted acc__hint">{{ t('At least 8 characters. Mix words, numbers and symbols.') }}</span>
          </div>
        </template>
        <p v-if="error" class="acc__error" role="alert">{{ error }}</p>
        <NButton type="submit" variant="primary" size="lg" block :busy="busy">{{ otpStep ? t('Verify') : mode === 'signup' ? t('Create account') : t('Sign in') }}</NButton>
        <a v-if="mode === 'signin' && !otpStep" class="acc__link" href="/login#forgot">{{ t('Forgot password?') }}</a>
        <p v-if="mode === 'signup'" class="muted acc__small">{{ t('No email or text messages are sent. You can shop without an account too.') }}</p>
      </form>
      <button type="button" class="acc__skip" @click="emit('go', 'home')">{{ t('Continue without an account') }}</button>
    </template>

    <!-- signed in -->
    <template v-else>
      <section class="acc__card">
        <span class="acc__avatar" aria-hidden="true">{{ initials }}</span>
        <span class="acc__who">
          <strong>{{ client.full_name }}</strong>
          <span class="muted">{{ client.email }}</span>
          <span v-if="client.mobile" class="muted num" dir="ltr">{{ client.mobile }}</span>
        </span>
        <button type="button" class="acc__icon" :aria-label="t('Edit profile')" @click="editing = { full_name: client.full_name, mobile: client.mobile }"><NIcon name="edit" /></button>
      </section>

      <section>
        <h2 class="acc__h2">{{ t('My purchases') }}</h2>
        <NState v-if="purchasesError" kind="error" :title="purchasesError" :retry="loadPurchases" />
        <NState v-else-if="!purchases" kind="loading" :title="t('Loading')" />
        <NState v-else-if="!purchases.length" kind="empty" icon="receipt" :title="t('No purchases yet')" :detail="t('Send your basket to a cashier while signed in, and your receipts appear here.')" />
        <ul v-else class="acc__list" role="list">
          <li v-for="p in purchases" :key="p.doctype + p.name">
            <button type="button" class="acc__row" @click="openReceipt(p)">
              <span class="acc__row-icon"><NIcon name="receipt" /></span>
              <span class="acc__row-main">
                <strong>{{ fmtDate(p.posting_date) }}<span v-if="p.is_return" class="acc__ret">{{ t('Return') }}</span></strong>
                <span class="muted num">{{ t('{0} items', p.total_qty) }} · {{ p.posting_time }}</span>
              </span>
              <strong class="num">{{ money(p.total, p.currency) }}</strong>
              <NIcon name="chevron" />
            </button>
          </li>
        </ul>
      </section>

      <NButton variant="ghost" icon="logout" block @click="signOut">{{ t('Sign out') }}</NButton>
    </template>

    <NSheet :open="!!receipt" :title="t('Receipt')" @close="receipt = null">
      <div v-if="receipt" class="acc__receipt">
        <header class="acc__r-head">
          <strong>{{ receipt.outlet }}</strong>
          <span class="muted num">{{ fmtDate(receipt.posting_date) }} · {{ receipt.posting_time }}</span>
          <span class="muted code">{{ receipt.name }}</span>
          <span v-if="receipt.is_return" class="acc__ret">{{ t('Return') }}</span>
        </header>
        <ul class="acc__r-items" role="list">
          <li v-for="(i, n) in receipt.items" :key="n">
            <span><strong>{{ i.item_name }}</strong><small class="muted num">{{ i.qty }} {{ i.uom }} × {{ money(i.rate, receipt.currency) }}</small></span>
            <span class="num">{{ money(i.amount, receipt.currency) }}</span>
          </li>
        </ul>
        <dl class="acc__r-sums">
          <div><dt>{{ t('Subtotal') }}</dt><dd class="num">{{ money(receipt.net_total, receipt.currency) }}</dd></div>
          <div v-if="receipt.discount"><dt>{{ t('Discount') }}</dt><dd class="num">− {{ money(receipt.discount, receipt.currency) }}</dd></div>
          <div v-for="(x, n) in receipt.taxes" :key="n"><dt>{{ x.description }}</dt><dd class="num">{{ money(x.amount, receipt.currency) }}</dd></div>
          <div class="acc__r-total"><dt>{{ t('Total') }}</dt><dd class="num">{{ money(receipt.total, receipt.currency) }}</dd></div>
          <div v-for="(p, n) in receipt.payments" :key="'p' + n"><dt>{{ p.mode }}</dt><dd class="num">{{ money(p.amount, receipt.currency) }}</dd></div>
          <div v-if="receipt.change"><dt>{{ t('Change') }}</dt><dd class="num">{{ money(receipt.change, receipt.currency) }}</dd></div>
        </dl>
      </div>
    </NSheet>

    <NSheet :open="!!editing" :title="t('Edit profile')" @close="editing = null">
      <form v-if="editing" class="acc__form" @submit.prevent="saveProfile">
        <label class="acc__field">{{ t('Full name') }}<input v-model="editing.full_name" class="acc__input" maxlength="140" autocomplete="name" /></label>
        <label class="acc__field">{{ t('Mobile number') }}<input v-model="editing.mobile" class="acc__input" type="tel" inputmode="tel" maxlength="20" dir="ltr" /></label>
      </form>
      <template #actions>
        <NButton @click="editing = null">{{ t('Cancel') }}</NButton>
        <NButton variant="primary" icon="check" :busy="saving" @click="saveProfile">{{ t('Save') }}</NButton>
      </template>
    </NSheet>
  </div>
</template>

<style>
.acc { display: grid; gap: var(--space-4); }
.acc__intro h1 { font-size: var(--text-2xl); color: var(--text-strong); line-height: var(--leading-tight); }
.acc__intro p { margin-block-start: var(--space-2); }
.acc__switch { display: grid; grid-template-columns: 1fr 1fr; padding: 4px; border-radius: var(--radius-pill); background: var(--surface-sunken); }
.acc__switch button { min-block-size: 44px; border: 0; border-radius: var(--radius-pill); background: transparent; color: var(--text-body); font: inherit; font-weight: 600; cursor: pointer; }
.acc__switch button[aria-selected='true'] { background: var(--surface-card); color: var(--text-strong); box-shadow: var(--shadow-raised); }
.acc__form { display: grid; gap: var(--space-4); }
.acc__field { display: grid; gap: 6px; font-size: var(--text-sm); font-weight: 600; color: var(--text-strong); }
.acc__input { inline-size: 100%; min-block-size: var(--touch-lg); padding-inline: var(--space-4); border: 1px solid var(--border-strong); border-radius: var(--radius-md); background: var(--surface-card); color: var(--text-strong); font: inherit; font-size: var(--text-md); font-weight: 400; }
.acc__input:focus-visible { outline: 3px solid var(--focus-ring); outline-offset: 1px; }
.acc__otp { letter-spacing: 0.3em; text-align: center; font-size: var(--text-xl); }
.acc__pwd { position: relative; display: block; }
.acc__pwd .acc__input { padding-inline-end: 84px; }
.acc__reveal { position: absolute; inset-block: 6px; inset-inline-end: 6px; min-inline-size: 64px; border: 0; border-radius: var(--radius-sm); background: var(--surface-sunken); color: var(--text-strong); font: inherit; font-size: var(--text-sm); font-weight: 600; cursor: pointer; }
.acc__hint { font-weight: 400; }
.acc__meter { display: flex; align-items: center; gap: 4px; font-weight: 600; }
.acc__meter i { flex: 1; block-size: 5px; border-radius: 3px; background: var(--surface-sunken); }
.acc__meter b { min-inline-size: 5em; text-align: end; font-size: var(--text-xs); }
.acc__meter--1 i:nth-child(-n + 1) { background: var(--danger-fg); }
.acc__meter--2 i:nth-child(-n + 2) { background: var(--warn-fg); }
.acc__meter--3 i:nth-child(-n + 3) { background: var(--ok-fg); }
.acc__meter--4 i { background: var(--ok-fg); }
.acc__error { color: var(--danger-fg); background: var(--danger-bg); padding: var(--space-3); border-radius: var(--radius-md); font-weight: 600; font-size: var(--text-sm); }
.acc__link { text-align: center; color: var(--text-body); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; min-block-size: var(--touch); display: grid; place-items: center; }
.acc__small { font-size: var(--text-sm); text-align: center; }
.acc__skip { border: 0; background: none; color: var(--text-muted); font: inherit; font-weight: 600; min-block-size: var(--touch); cursor: pointer; }
.acc__card { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-radius: var(--radius-lg); background: var(--brand-fill); color: var(--brand-on-fill); }
.acc__avatar { inline-size: 56px; block-size: 56px; border-radius: 50%; display: grid; place-items: center; background: var(--nest-ink-900); color: var(--nest-yellow-400); font-weight: 700; font-size: var(--text-lg); flex: none; }
.acc__who { flex: 1; min-inline-size: 0; display: grid; }
.acc__who strong { font-size: var(--text-lg); }
.acc__who .muted { color: inherit; opacity: 0.75; overflow: hidden; text-overflow: ellipsis; }
.acc__icon { inline-size: var(--touch); block-size: var(--touch); border: 0; border-radius: 50%; background: rgb(255 255 255 / 0.5); color: inherit; display: grid; place-items: center; cursor: pointer; flex: none; }
.acc__h2 { font-size: var(--text-md); color: var(--text-strong); margin-block-end: var(--space-2); }
.acc__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.acc__row { inline-size: 100%; display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); background: var(--surface-card); color: var(--text-strong); font: inherit; cursor: pointer; text-align: start; }
.acc__row-icon { inline-size: 40px; block-size: 40px; border-radius: var(--radius-md); background: var(--surface-sunken); display: grid; place-items: center; flex: none; }
.acc__row-main { flex: 1; min-inline-size: 0; display: grid; }
.acc__ret { margin-inline-start: var(--space-2); font-size: var(--text-xs); padding: 1px 8px; border-radius: var(--radius-pill); background: var(--warn-bg); color: var(--warn-fg); }
.acc__receipt { display: grid; gap: var(--space-4); }
.acc__r-head { display: grid; justify-items: center; text-align: center; gap: 2px; padding-block-end: var(--space-3); border-block-end: 1px dashed var(--border-strong); }
.acc__r-items { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.acc__r-items li { display: flex; justify-content: space-between; gap: var(--space-3); }
.acc__r-items li > span:first-child { display: grid; }
.acc__r-sums { margin: 0; display: grid; gap: 4px; padding-block-start: var(--space-3); border-block-start: 1px dashed var(--border-strong); }
.acc__r-sums div { display: flex; justify-content: space-between; }
.acc__r-sums dd { margin: 0; }
.acc__r-total { font-size: var(--text-lg); font-weight: 700; color: var(--text-strong); padding-block: var(--space-2); border-block: 1.5px solid var(--text-strong); margin-block: var(--space-1); }
</style>
