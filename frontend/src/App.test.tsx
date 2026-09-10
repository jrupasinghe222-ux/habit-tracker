import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Session } from '@supabase/supabase-js'
import { App } from './App'

const auth = vi.hoisted(() => ({ callback: null as null | ((event: string, next: Session | null) => void) }))
vi.mock('./supabase', () => ({ supabase: { auth: {
  onAuthStateChange: (callback: typeof auth.callback) => { auth.callback = callback; return { data: { subscription: { unsubscribe() {} } } } },
  signOut: async () => { auth.callback?.('SIGNED_OUT', null); return { error: null } },
  signInWithOAuth: async () => ({ error: null }),
} } }))
function session(id = 'a', token = 'token-a') { return { user: { id }, access_token: token } as Session }
function calendar(name = 'Read', date = '2026-09-10') {
  return { date, today: '2026-09-10', timezone: 'Asia/Colombo', tasks: [{ id: 'task-a', name, completed: false }],
    history: Array.from({ length: 7 }, (_, i) => ({ date: `2026-09-${String(i + 4).padStart(2, '0')}`, total: 1, completed_ids: [] })) }
}
const ok = (data = calendar()) => ({ ok: true, status: 200, json: async () => data }) as Response
const emit = (next: Session | null, event = 'SIGNED_IN') => act(() => auth.callback?.(event, next))
async function open() { render(<App />); emit(session()); await screen.findByRole('heading', { name: 'Read' }) }

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok()))
  Element.prototype.scrollIntoView = vi.fn()
  window.matchMedia = vi.fn().mockReturnValue({ matches: false })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('request and account reliability', () => {
  it('keeps an edit draft and focus when the same account refreshes its token', async () => {
    await open()
    fireEvent.click(screen.getByRole('button', { name: 'Edit Read' }))
    const input = screen.getByRole('textbox', { name: 'Edit task' }) as HTMLInputElement
    fireEvent.change(input, { target: { value: 'Unfinished draft' } })
    emit(session('a', 'new-token'), 'TOKEN_REFRESHED')
    expect(input.value).toBe('Unfinished draft')
    expect(document.activeElement).toBe(input)
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Edit Read' }))
    fireEvent.focus(window)
    await waitFor(() => expect(vi.mocked(fetch).mock.calls.at(-1)?.[1]?.headers).toEqual({ Authorization: 'Bearer new-token' }))
  })

  it('ignores a delayed response from the previous account', async () => {
    let resolveOld!: (response: Response) => void
    vi.mocked(fetch).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve })).mockResolvedValue(ok(calendar('Account B task')))
    render(<App />)
    emit(session())
    emit(session('b', 'token-b'))
    await screen.findByRole('heading', { name: 'Account B task' })
    await act(async () => resolveOld(ok(calendar('Private account A task'))))
    expect(screen.queryByText('Private account A task')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Account B task' })).toBeTruthy()
  })

  it('clears visible tasks and drafts on sign-out', async () => {
    await open()
    fireEvent.change(screen.getByRole('textbox', { name: 'Add a task for this day' }), { target: { value: 'Private draft' } })
    emit(null, 'SIGNED_OUT')
    expect(screen.queryByRole('heading', { name: 'Read' })).toBeNull()
    expect(screen.queryByDisplayValue('Private draft')).toBeNull()
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeTruthy()
  })

  it('recovers from a failed save on the next background refresh', async () => {
    await open()
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    fireEvent.click(screen.getByRole('button', { name: 'Mark done: Read on 2026-09-10' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('alert').textContent).toContain('Check your connection')
    vi.mocked(fetch).mockResolvedValue(ok(calendar('Recovered task')))
    fireEvent.focus(window)
    await screen.findByRole('heading', { name: 'Recovered task' })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('ignores an earlier calendar response after navigating to another day', async () => {
    await open()
    let resolveOld!: (response: Response) => void
    vi.mocked(fetch).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
    fireEvent.focus(window)
    vi.mocked(fetch).mockResolvedValue(ok(calendar('Yesterday task', '2026-09-09')))
    fireEvent.click(screen.getByRole('button', { name: 'Previous day' }))
    await screen.findByRole('heading', { name: 'Yesterday task' })
    await act(async () => resolveOld(ok(calendar('Old response'))))
    expect(screen.queryByText('Old response')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Tasks for 2026-09-09' })).toBeTruthy()
  })

  it('keeps a failed create retry idempotent and disables repeat clicks while saving', async () => {
    await open()
    let rejectSave!: (reason: Error) => void
    vi.mocked(fetch).mockReturnValueOnce(new Promise((_, reject) => { rejectSave = reject }))
    fireEvent.change(screen.getByRole('textbox', { name: 'Add a task for this day' }), { target: { value: 'Walk' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
    expect((screen.getByRole('button', { name: 'Saving…' }) as HTMLButtonElement).disabled).toBe(true)
    const firstBody = vi.mocked(fetch).mock.calls.at(-1)?.[1]?.body
    await act(async () => rejectSave(new TypeError('offline')))
    vi.mocked(fetch).mockResolvedValue(ok())
    fireEvent.click(screen.getByRole('button', { name: 'Add task' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Saving…' })).toBeNull())
    const posts = vi.mocked(fetch).mock.calls.filter(call => call[1]?.method === 'POST')
    expect(posts).toHaveLength(2)
    expect(posts[1][1]?.body).toBe(firstBody)
  })
})
