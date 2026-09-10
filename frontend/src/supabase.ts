import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
const configured = typeof url === 'string' && /^https:\/\/[a-z0-9]+\.supabase\.co$/.test(url)
  && typeof key === 'string' && key.startsWith('sb_publishable_') && !key.includes('REPLACE')

export const supabase = configured ? createClient(url, key, {
  auth: {
    flowType: 'pkce',
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    // Use Supabase's default localStorage so sign-in survives closing the tab.
    // The SDK manages persistence, token refresh, and cross-tab sign-out.
  },
}) : null
