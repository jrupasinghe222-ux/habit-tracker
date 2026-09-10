import { StrictMode, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { createRoot } from 'react-dom/client'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { HabitCard } from './HabitCard'
import { DeleteHabitDialog } from './DeleteHabitDialog'
import { WeeklyProgress } from './WeeklyProgress'
import './styles.css'

type Task = { id: string; name: string; completed: boolean }
type Calendar = { date: string; today: string; timezone: string; tasks: Task[];
  history: { date: string; total: number; completed_ids: string[] }[] }

function shiftDay(value: string, delta: number) {
  const day = new Date(`${value}T12:00:00Z`)
  day.setUTCDate(day.getUTCDate() + delta)
  return day.toISOString().slice(0, 10)
}

function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(!supabase)
  const [selected, setSelected] = useState('')
  const [calendar, setCalendar] = useState<Calendar | null>(null)
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Task | null>(null)
  const [deleteError, setDeleteError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const generation = useRef(0)
  const mutation = useRef(false)
  const requestId = useRef<{ name: string; day: string; id: string } | null>(null)
  const completedCount = calendar?.tasks.filter(task => task.completed).length ?? 0

  useEffect(() => {
    if (!supabase) return
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      if (next && window.location.pathname === '/auth/callback') window.history.replaceState(window.history.state, '', '/')
      setSession(next)
      setReady(true)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    setSelected('')
    setName('')
    setDeleteTarget(null)
    setDeleteError('')
    requestId.current = null
  }, [session?.user.id])

  useEffect(() => {
    const version = ++generation.current
    mutation.current = false
    setBusy(null)
    setCalendar(null)
    setMessage('')
    if (!session) { setLoading(false); return }
    const controller = new AbortController()
    let read = 0
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    async function load(initial = false) {
      if (mutation.current) return
      const attempt = ++read
      if (initial) setLoading(true)
      try {
        const params = new URLSearchParams({ timezone })
        if (selected) params.set('selected', selected)
        const response = await fetch(`/api/calendar?${params}`, {
          headers: { Authorization: `Bearer ${session!.access_token}` }, cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
        })
        if (!response.ok) throw new Error(response.status === 401 ? 'Your session could not be verified. Please sign in again.' : 'Could not load this day. Please retry.')
        const data = await response.json()
        if (typeof data.date !== 'string' || typeof data.today !== 'string' || typeof data.timezone !== 'string'
          || !Array.isArray(data.tasks) || !data.tasks.every((task: Task) => typeof task.id === 'string' && typeof task.name === 'string' && typeof task.completed === 'boolean')
          || !Array.isArray(data.history) || data.history.length !== 7 || !data.history.every((day: Calendar['history'][number]) =>
            typeof day.date === 'string' && Number.isInteger(day.total) && day.total >= 0 && Array.isArray(day.completed_ids)
            && day.completed_ids.every(id => typeof id === 'string'))) throw new Error('Unexpected response. Please reload.')
        if (generation.current === version && read === attempt && !mutation.current) { setCalendar(data); setMessage('') }
      } catch (error) {
        if (!controller.signal.aborted && generation.current === version && read === attempt && !mutation.current) {
          setMessage(error instanceof Error ? error.message : 'Could not load this day.')
        }
      } finally { if (generation.current === version) setLoading(false) }
    }
    void load(true)
    const timer = window.setInterval(() => { if (!document.hidden) void load() }, 30000)
    const visible = () => { if (!document.hidden) void load() }
    window.addEventListener('focus', visible)
    document.addEventListener('visibilitychange', visible)
    return () => { generation.current++; controller.abort(); window.clearInterval(timer);
      window.removeEventListener('focus', visible); document.removeEventListener('visibilitychange', visible) }
  }, [session?.access_token, selected, refresh])

  function chooseDay(day: string) {
    if (mutation.current || day === selected) return
    document.getElementById("habits-title")?.scrollIntoView({ behavior: "smooth", block: "start" })
    generation.current++
    setSelected(day)
    setCalendar(null)
    setName('')
    setDeleteTarget(null)
    requestId.current = null
  }

  async function signIn() {
    const result = await supabase?.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: `${window.location.origin}/auth/callback` } })
    if (result?.error) setMessage('Could not start Google sign-in. Please try again.')
  }

  async function saveTask(method: string, taskId: string | null, body?: object): Promise<boolean> {
    if (!session || !calendar || mutation.current) return false
    const version = ++generation.current
    const day = calendar.date
    mutation.current = true
    setBusy(taskId ?? 'new')
    setMessage('')
    setDeleteError('')
    try {
      const suffix = taskId ? `/${taskId}` : ''
      const response = await fetch(`/api/days/${day}/tasks${suffix}?timezone=${encodeURIComponent(calendar.timezone)}`, {
        method, headers: { Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(15000),
      })
      if (!response.ok && !(method === 'DELETE' && response.status === 404)) {
        let detail = 'Could not save this change. Reload this day before trying again.'
        if (response.status === 409) { const data = await response.json(); if (typeof data.detail === 'string') detail = data.detail }
        throw new Error(detail)
      }
      if (version !== generation.current) return false
      setDeleteTarget(null)
      setRefresh(value => value + 1)
      return true
    } catch (error) {
      if (version === generation.current) {
        const text = error instanceof Error && error.name !== 'TimeoutError' ? error.message : 'Could not confirm the save. Reload this day before retrying.'
        if (method === 'DELETE') setDeleteError(text)
        else setMessage(text)
      }
      return false
    } finally { if (version === generation.current) { mutation.current = false; setBusy(null) } }
  }

  async function addTask(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || !calendar) return
    if (requestId.current?.name !== name.trim() || requestId.current?.day !== calendar.date) {
      requestId.current = { name: name.trim(), day: calendar.date, id: crypto.randomUUID() }
    }
    if (await saveTask('POST', null, { name: name.trim(), id: requestId.current.id })) { setName(''); requestId.current = null }
  }

  return <main>
    <header className="topbar"><span className="eyebrow">Habit Tracker</span>
      {session && <button className="secondary" onClick={() => void supabase?.auth.signOut({ scope: 'local' }).then(({ error }) => { if (error) setMessage('Could not sign out. Please retry.') })}>Sign out</button>}
    </header>
    <h1>One small step,<br />every day.</h1>
    <p className="intro">Make room for the things you want to do more often.</p>
    {!ready ? <p role="status">Checking your session…</p> : !supabase ? <section><h2>Google sign-in is being set up</h2></section>
      : !session ? <section><h2>Your habits, in one place</h2><p>Sign in to create habits and keep them saved to your account.</p>
        <button onClick={() => void signIn()}>Continue with Google</button></section>
      : <>
        <section aria-labelledby="habits-title">
          <h2 id="habits-title">{calendar ? (calendar.date !== calendar.today ? `Tasks for ${calendar.date}` : 'Your tasks today') : selected ? `Tasks for ${selected}` : 'Your tasks today'}</h2>
          {calendar && <>
            <div className="date-navigation">
              <button type="button" className="secondary" disabled={busy !== null || calendar.date <= '2000-01-01'} onClick={() => chooseDay(shiftDay(calendar.date, -1))} aria-label="Previous day">←</button>
              <input type="date" aria-label="Selected day" value={calendar.date} min="2000-01-01" max={calendar.today} disabled={busy !== null}
                onChange={event => { if (event.target.value && event.target.value <= calendar.today && event.target.value >= '2000-01-01') chooseDay(event.target.value) }} />
              <button type="button" className="secondary" disabled={busy !== null || calendar.date >= calendar.today} onClick={() => chooseDay(shiftDay(calendar.date, 1))} aria-label="Next day">→</button>
              <button type="button" className="secondary" disabled={busy !== null} onClick={() => chooseDay('')}>Today</button>
            </div>
            <p className="date-scope">Changes apply only to {calendar.date === calendar.today ? 'today' : calendar.date}.</p>
            <div className="daily-progress"><div className="progress-heading"><strong>{completedCount} of {calendar.tasks.length} done</strong><span>{calendar.timezone.replaceAll('_', ' ')}</span></div>
              <progress value={completedCount} max={Math.max(calendar.tasks.length, 1)} aria-label="Selected day's task completion" /></div>
            <form onSubmit={event => void addTask(event)}><label htmlFor="habit-name">Add a task for this day</label><div className="input-row">
              <input id="habit-name" value={name} onChange={event => setName(event.target.value)} maxLength={80} required placeholder="For example, read for 10 minutes" />
              <button disabled={busy !== null || !name.trim()}>{busy === 'new' ? 'Saving…' : 'Add task'}</button></div></form>
            {calendar.tasks.length ? <ul className="habits">{calendar.tasks.map(task => <HabitCard key={`${calendar.date}:${task.id}`} habit={task}
              completed={task.completed} checkingIn={busy === task.id} checkInDisabled={busy !== null} deleting={busy === task.id && deleteTarget !== null}
              deleteBusy={busy !== null} dateLabel={calendar.date} onCheckIn={() => void saveTask('PATCH', task.id, { completed: !task.completed })}
              onSave={(id, value) => saveTask('PATCH', id, { name: value })} onDelete={() => { setDeleteTarget(task); setDeleteError('') }} />)}</ul>
              : <p>No tasks for this day. Add one above.</p>}
          </>}
          {loading && <p role="status">Loading your day…</p>}
          <button className="secondary reload-habits" disabled={loading || busy !== null} onClick={() => setRefresh(value => value + 1)}>Reload tasks</button>
        </section>
        {calendar && <WeeklyProgress days={calendar.history} selectedDate={calendar.date} today={calendar.today} disabled={busy !== null} onSelect={chooseDay} />}
      </>}
    {deleteTarget && calendar && <DeleteHabitDialog name={deleteTarget.name} dateLabel={calendar.date} busy={busy !== null} error={deleteError}
      onCancel={() => { if (!mutation.current) setDeleteTarget(null) }} onConfirm={() => void saveTask('DELETE', deleteTarget.id)} />}
    {message && <p className="notice" role="alert">{message}</p>}
    <p className="note">Small steps count. Check in each day and build your history.</p>
  </main>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
