import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { postbuild } from '../src/shared/build/postbuild.mjs'

const frontendDir = join(dirname(fileURLToPath(import.meta.url)), '..')

postbuild({
  app: 'nest_pos',
  frontendDir,
  workerTemplate: join(frontendDir, 'src', 'shared', 'sw', 'worker.js'),
  surfaces: [
    {
      entry: 'staff',
      page: 'nest-pos',
      route: '/nest-pos',
      name: 'Nest POS',
      shortName: 'Nest POS',
      description: 'Retail till for ERPNext',
      background: '#f4f5f6',
      theme: '#1e1d1d',
      cachePrefix: 'nestpos-staff-',
      splash: { logo: 'nest-pos-logo.png', tagline: 'Retail till for ERPNext' },
      exclude: ['/nest-pos/customer'],
      shortcuts: [{ name: 'Sell', url: '/nest-pos/sell' }, { name: 'Client baskets', url: '/nest-pos/baskets' }],
    },
    {
      entry: 'customer',
      page: 'nest-pos-customer',
      route: '/nest-pos/customer',
      name: 'Nest Shop',
      shortName: 'Nest Shop',
      description: 'Check prices and send your basket to the till',
      background: '#ffde59',
      theme: '#ffde59',
      cachePrefix: 'nestpos-cust-',
      splash: { logo: 'nest-pos-logo.png', tagline: 'Scan, check prices, skip the wait' },
    },
  ],
})
