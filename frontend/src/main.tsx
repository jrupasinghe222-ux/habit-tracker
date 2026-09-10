import { StrictMode, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { HabitCard } from './HabitCard'
import { DeleteHabitDialog } from './DeleteHabitDialog'
import './styles.css'

type Habit = { id: string; name: string }

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(!supabase)
  const [habits, setHabits] = useState<Habit[]>([])
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [pendingDelete, setPendingDelete] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Habit | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const generation = useRef(0)

  useEffect(() => {
    if (!supabase) return
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      generation.current += 1
      setSession(next)
      setReady(true)
      setHabits([])
      setMessage('')
      setName('')
      setSaving(false)
      setPendingDelete(null)
      setDeleteTarget(null)
      setDeleteError('')
    })
    return () => { generation.current += 1; data.subscription.unsubscribe() }
  }, [])

  useEffect(() => {
    if (!session) { setLoading(false); return }
    let active = true
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setLoading(true)
    setMessage('')
    fetch('/api/habits', {
      headers: { Authorization: `Bearer ${session.access_token}` },
      signal: controller.signal, cache: 'no-store',
    }).then(async response => {
      if (!response.ok) throw new Error(response.status === 401
        ? 'Your session could not be verified. Sign out and sign in again.'
        : 'Your habits could not be loaded. Please try again.')
      const rows: unknown = await response.json()
      if (!Array.isArray(rows) || !rows.every(row => row && typeof row.id === 'string' && typeof row.name === 'string')) {
        throw new Error('Unexpected response. Please try again.')
      }
      if (active) setHabits(rows)
    }).catch(error => {
      if (active) setMessage(error.name === 'AbortError' ? 'The request took too long. Please retry.' : error.message)
    }).finally(() => { window.clearTimeout(timeout); if (active) setLoading(false) })
    return () => { active = false; controller.abort(); window.clearTimeout(timeout) }
  }, [session, refresh])

  async function signIn() {
    if (!supabase) return
    setMessage('')
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    })
    if (error) setMessage('Could not start Google sign-in. Please try again.')
  }

  async function signOut() {
    if (!supabase) return
    const { error } = await supabase.auth.signOut({ scope: 'local' })
    if (error) setMessage('Could not complete sign-out. Please try again.')
  }

  async function createHabit(event: FormEvent) {
    event.preventDefault()
    if (!session || saving || !name.trim()) return
    const version = generation.current
    setSaving(true)
    setMessage('')
    try {
      const response = await fetch('/api/habits', {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
        signal: AbortSignal.timeout(10000),
      })
      if (!response.ok) throw new Error('Could not save this habit. Please try again.')
      if (version === generation.current) { setName(''); setRefresh(value => value + 1) }
    } catch (error) {
      if (version === generation.current) setMessage(error instanceof Error && error.name === 'TimeoutError'
        ? 'The save timed out. Reload your habits before retrying to avoid a duplicate.'
        : 'Could not save this habit. Please try again.')
    } finally { if (version === generation.current) setSaving(false) }
  }

  async function updateHabit(id: string, nextName: string): Promise<boolean> {
    if (!session) return false
    const version = generation.current
    setMessage('')
    try {
      const response = await fetch(`/api/habits/${id}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nextName }),
        signal: AbortSignal.timeout(10000),
      })
      if (!response.ok) throw new Error()
      const updated: Habit = await response.json()
      if (version !== generation.current) return false
      setHabits(rows => rows.map(row => row.id === id ? updated : row))
      return true
    } catch {
      if (version === generation.current) setMessage('Could not confirm the update. Your edit is still here; try again or reload your habits.')
      return false
    }
  }
  async function deleteHabit(habit: Habit) {
    if (!session || pendingDelete) return
    const version = generation.current
    setPendingDelete(habit.id)
    setDeleteError('')
    setMessage('')
    try {
      const response = await fetch(`/api/habits/${habit.id}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${session.access_token}` },
        signal: AbortSignal.timeout(10000),
      })
      if (!response.ok && response.status !== 404) throw new Error()
      if (version === generation.current) {
        setHabits(rows => rows.filter(row => row.id !== habit.id))
        setDeleteTarget(null)
      }
    } catch {
      if (version === generation.current) setDeleteError('Could not confirm deletion. Please try again, or cancel and reload your habits.')
    } finally { if (version === generation.current) setPendingDelete(null) }
  }

  return (
    <main>
      <header className="topbar">
        <span className="eyebrow">Habit Tracker</span>
        {session && <button className="secondary" onClick={() => void signOut()}>Sign out</button>}
      </header>
      <h1>One small step,<br />every day.</h1>
      <p className="intro">Make room for the things you want to do more often.</p>
      {!ready ? <p role="status">Checking your session…</p> : !supabase ? (
        <section>
          <h2>Google sign-in is being set up</h2>
          <p>This app is not open for registration yet. Please check back soon.</p>
        </section>
      ) : !session ? (
        <section>
          <h2>Your habits, in one place</h2>
          <p>Sign in to create habits and keep them saved to your account.</p>
          <button onClick={() => void signIn()}>Continue with Google</button>
        </section>
      ) : (
        <section aria-labelledby="habits-title">
          <h2 id="habits-title">Your habits</h2>
          <form onSubmit={event => void createHabit(event)}>
            <label htmlFor="habit-name">Add a daily habit</label>
            <div className="input-row">
              <input id="habit-name" value={name} onChange={event => setName(event.target.value)}
                maxLength={80} required placeholder="For example, read for 10 minutes" />
              <button disabled={saving || !name.trim()}>{saving ? 'Saving…' : 'Add habit'}</button>
            </div>
          </form>
          {loading ? <p role="status">Loading your habits…</p> : (
            habits.length ? <ul className="habits">{habits.map(habit => (
              <HabitCard key={habit.id} habit={habit} deleting={pendingDelete === habit.id}
                deleteBusy={pendingDelete !== null} onSave={updateHabit}
                onDelete={() => { setDeleteError(''); setDeleteTarget(habit) }} />
            ))}</ul> : !message && <p>No habits yet. Add your first one above.</p>
          )}
          <button className="secondary reload-habits" disabled={loading} onClick={() => setRefresh(value => value + 1)}>Reload habits</button>
        </section>
      )}
      {deleteTarget && <DeleteHabitDialog name={deleteTarget.name} busy={pendingDelete !== null}
        error={deleteError} onCancel={() => { if (!pendingDelete) setDeleteTarget(null) }}
        onConfirm={() => void deleteHabit(deleteTarget)} />}
      {message && <p className="notice" role="alert">{message}</p>}
      <p className="note">Early version · Daily check-ins and progress tracking are coming next.</p>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
