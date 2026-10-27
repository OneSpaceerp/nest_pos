<script setup lang="ts">
import { computed, onMounted, provide, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import NConnection from '@shared/components/NConnection.vue'
import NShell from '@shared/components/NShell.vue'
import NState from '@shared/components/NState.vue'
import NToasts from '@shared/components/NToasts.vue'
import { call } from '@shared/lib/api'
import { t } from '@shared/lib/i18n'
import { purgeLocal } from '@shared/lib/pwa'
import { connect, on, onReconnect, subscribeDoc } from '@shared/lib/realtime'
import { cycleTheme, toggleLanguage } from '@shared/app/surface'
import RegisterGate from '@shared/till/RegisterGate.vue'
import { POS_API, useTill } from './state'

const props = defineProps<{ embedded?: boolean; root: HTMLElement }>()
const till = useTill()
const route = useRoute()
const bootError = ref('')
const basketCount = ref(0)
provide('embedded', props.embedded ?? false)

const nav = computed(() => [
  { to: '/sell', label: t('Sell'), icon: 'scan' },
  { to: '/baskets', label: t('Baskets'), icon: 'basket', badge: basketCount.value || undefined },
  { to: '/sales', label: t('Sales'), icon: 'receipt' },
  { to: '/shift', label: t('Shift'), icon: 'register' },
  { to: '/phone-scanner', label: t('Phone'), icon: 'phone' },
])
const needsShift = computed(() => !['pair', 'sync'].includes(String(route.name)))

async function start() {
  bootError.value = ''
  try {
    await till.loadBoot()
  } catch (e) {
    bootError.value = (e as Error).message
  }
}

async function refreshBaskets() {
  if (!till.registerName.value) return
  try {
    const rows = await call<{ status: string }[]>(POS_API('baskets.inbox'), { register_name: till.registerName.value }, { method: 'GET' })
    basketCount.value = rows.filter((r) => r.status === 'Submitted').length
  } catch {
    /* badge only */
  }
}

let unsub: (() => void) | null = null
watch(till.registerName, (name) => {
  unsub?.()
  if (!name) return
  unsub = subscribeDoc('Nest POS Register', name)
  void refreshBaskets()
})

onMounted(async () => {
  const boot = window.nest_boot as { site_name?: string; socketio_port?: number } | undefined
  await connect(boot?.site_name ?? location.hostname, boot?.socketio_port)
  on('nest_pos:basket', () => void refreshBaskets())
  onReconnect(() => void refreshBaskets())
  await start()
})

async function logout() {
  if (till.pendingCount.value) {
    alert(t('{0} sale(s) have not synced yet. Stay signed in until they do, or export them from Sync.', till.pendingCount.value))
    return
  }
  await call('logout', {}, { method: 'POST' }).catch(() => undefined)
  await purgeLocal('nest_pos')
  await purgeLocal('nestpos-staff-')
  location.href = '/login?redirect-to=/nest-pos'
}
</script>

<template>
  <NShell
    title="Nest POS"
    logo="/assets/nest_pos/images/nest-pos-logo.png"
    :nav="nav"
    :embedded="embedded"
    desk-url="/desk/nest-pos"
    :user="till.boot.value?.user"
    @lang="toggleLanguage('nest_pos', root)"
    @theme="cycleTheme('nest_pos', root)"
    @logout="logout"
  >
    <template #status>
      <span v-if="till.registerName.value" class="app__reg">{{ till.registerName.value }}</span>
      <NConnection
        :online="till.online.value"
        :pending="till.pendingCount.value"
        :review="till.reviewCount.value"
        :syncing="till.syncing.value"
        :busy="till.cart.lines.length > 0"
        @open="$router.push('/sync')"
      />
    </template>
    <nav v-if="embedded" class="app__tabs" :aria-label="t('Till sections')">
      <RouterLink v-for="n in nav" :key="n.to" :to="n.to" class="app__tab">{{ n.label }}<span v-if="n.badge" class="app__badge num">{{ n.badge }}</span></RouterLink>
    </nav>
    <NState v-if="bootError" kind="error" :title="t('The till could not start')" :detail="bootError" :retry="start" />
    <RegisterGate v-else-if="needsShift && !till.sessionOpen.value" :till="till" />
    <RouterView v-else v-slot="{ Component }">
      <component :is="Component" />
    </RouterView>
  </NShell>
  <NToasts />
</template>

<style>
#app, .nest-desk-host > div { block-size: 100%; }
.app__reg { font-weight: 600; font-size: var(--text-sm); color: var(--text-muted); white-space: nowrap; }
@media (max-width: 480px) { .app__reg { display: none; } }
.app__tabs { display: flex; gap: var(--space-1); padding: 0 var(--space-4) var(--space-2); border-block-end: 1px solid var(--border-subtle); overflow-x: auto; }
.app__tab { min-block-size: 40px; display: inline-flex; align-items: center; gap: 6px; padding-inline: var(--space-3); border-radius: var(--radius-md); color: var(--text-body); text-decoration: none; font-weight: 500; white-space: nowrap; }
.app__tab.router-link-active { background: var(--brand-fill); color: var(--brand-on-fill); }
.app__badge { min-inline-size: 20px; block-size: 20px; border-radius: 10px; background: var(--danger-fg); color: #fff; font-size: var(--text-xs); display: inline-grid; place-items: center; padding-inline: 5px; }
</style>
