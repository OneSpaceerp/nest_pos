import { createTill, type Till } from '@shared/till/till'

let till: Till | null = null

export function useTill(): Till {
  if (!till) till = createTill('nest_pos', (window.nest_boot as { site_name?: string } | undefined)?.site_name ?? location.hostname)
  return till
}

export const POS_API = (m: string) => `nest_pos.api.${m}`
