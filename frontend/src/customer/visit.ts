// One store visit for the shopper app: the opaque session token, the basket being built, the basket
// sent to the till, and the prices checked so far. Kept in localStorage so a reload or a lost response
// never loses the basket (the request key is reused on retry, so the server returns the same basket).
import { computed, reactive, ref, watch } from 'vue'
import { toast } from '@shared/components/toast'
import { ApiError, call, newKey } from '@shared/lib/api'
import { t } from '@shared/lib/i18n'

export const API = (m: string) => `nest_pos.api.client.${m}`
export const ACCOUNT_API = (m: string) => `nest_pos.api.account.${m}`
const STORE_KEY = 'nest_pos_customer:visit'

export interface PriceView { status: string; item_code: string; item_name: string; image?: string; description?: string; uom: string; rate: number; currency: string; price_includes_tax: boolean | null; availability: 'in_stock' | 'low' | 'out' | null }
export interface Line { item_code: string; item_name: string; qty: number; rate: number; image?: string }
export interface BasketStatus { status: string; handoff_code: string; total_preview: number }
export interface Client { full_name: string; email: string; mobile: string; customer: string }
interface Visit { token: string; outlet: string; register: string; currency: string; lines: Line[]; pendingKey: string | null; basket: string | null; recent: PriceView[] }

export const client = ref<Client | null>(((window as unknown as { nest_boot?: { client?: Client | null } }).nest_boot?.client) ?? null)
export const signedInElsewhere = Boolean((window as unknown as { nest_boot?: { signed_in?: boolean } }).nest_boot?.signed_in) && !client.value

export const visit = reactive<Visit>({ token: '', outlet: '', register: '', currency: 'USD', lines: [], pendingKey: null, basket: null, recent: [] })
try {
  Object.assign(visit, JSON.parse(localStorage.getItem(STORE_KEY) ?? '{}'))
} catch { /* fresh visit */ }
watch(visit, () => {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(visit)) } catch { /* private mode */ }
}, { deep: true })

export const status = ref<BasketStatus | null>(null)
export const sending = ref(false)
export const needsStore = ref(false)
/** which account form to show first; #signin / #signup links set it */
export const accountMode = ref<'signin' | 'signup'>(location.hash === '#signin' ? 'signin' : 'signup')
export const total = computed(() => visit.lines.reduce((a, l) => a + l.qty * l.rate, 0))
export const count = computed(() => visit.lines.reduce((a, l) => a + l.qty, 0))
export const FINAL = ['Completed', 'Cancelled', 'Expired']

let pollTimer = 0

async function guarded<T>(fn: () => Promise<T>): Promise<T | undefined> {
  try {
    return await fn()
  } catch (e) {
    if (e instanceof ApiError && e.kind === 'permission' && visit.token) {
      toast(e.message, 'warn')
      Object.assign(visit, { token: '', basket: null, pendingKey: null })
      needsStore.value = true
      return undefined
    }
    toast((e as Error).message, 'danger')
    return undefined
  }
}

export async function startVisit(args: { register_name?: string; store_code?: string }) {
  const res = await call<{ token: string; outlet: string; register: string }>(API('start'), args)
  Object.assign(visit, { token: res.token, outlet: res.outlet, register: res.register, lines: visit.register === res.register ? visit.lines : [], recent: visit.register === res.register ? visit.recent : [], basket: null, pendingKey: null })
  status.value = null
  needsStore.value = false
}

export async function checkPrice(code: string): Promise<PriceView | null> {
  if (!visit.token) {
    needsStore.value = true
    return null
  }
  const res = await guarded(() => call<PriceView>(API('price'), { token: visit.token, code }))
  if (!res) return null
  if (res.status !== 'ok') {
    toast(t('We couldn’t find that product. Ask a member of staff.'), 'warn')
    return null
  }
  visit.currency = res.currency
  visit.recent = [res, ...visit.recent.filter((r) => r.item_code !== res.item_code)].slice(0, 12)
  return res
}

export function addToBasket(p: Pick<PriceView, 'item_code' | 'item_name' | 'rate' | 'image'>, qty = 1) {
  if (visit.basket && status.value && !FINAL.includes(status.value.status)) {
    toast(t('Your last basket is still with the till. Start a new one when it’s done.'), 'warn')
    return false
  }
  if (visit.basket) Object.assign(visit, { basket: null, pendingKey: null })
  const existing = visit.lines.find((l) => l.item_code === p.item_code)
  if (existing) existing.qty += qty
  else visit.lines.push({ item_code: p.item_code, item_name: p.item_name, qty, rate: p.rate, image: p.image })
  return true
}

export async function sendBasket() {
  sending.value = true
  visit.pendingKey ??= newKey('basket-')
  const res = await guarded(() =>
    call<BasketStatus & { basket: string }>(API('submit'), {
      token: visit.token,
      lines: visit.lines.map((l) => ({ item_code: l.item_code, qty: l.qty })),
      request_key: visit.pendingKey,
    }, { timeoutMs: 20000 }),
  )
  sending.value = false
  if (!res) return false
  visit.basket = res.basket
  visit.pendingKey = null
  status.value = res
  schedulePoll()
  return true
}

export async function refreshStatus() {
  if (!visit.basket || !visit.token) return
  const res = await guarded(() => call<BasketStatus>(API('status'), { token: visit.token, basket: visit.basket }))
  if (res) {
    status.value = res
    if (res.status === 'Completed') visit.lines = []
  }
  schedulePoll()
}
function schedulePoll() {
  clearTimeout(pollTimer)
  if (!status.value || FINAL.includes(status.value.status)) return
  pollTimer = window.setTimeout(refreshStatus, 4000)
}
export function stopPolling() {
  clearTimeout(pollTimer)
}

export async function cancelBasket() {
  const res = await guarded(() => call<BasketStatus>(API('cancel'), { token: visit.token, basket: visit.basket }))
  if (res) status.value = res
}

export function newBasket() {
  Object.assign(visit, { lines: [], basket: null, pendingKey: null })
  status.value = null
}
