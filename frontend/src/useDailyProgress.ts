import { useCallback, useEffect, useRef, useState } from 'react'

export type HistoryDay = { date: string; completed_ids: string[]; total: number }
type Today = { date: string; timezone: string; completed_ids: string[]; history: HistoryDay[] }

export function useDailyProgress(token: string | undefined, refresh: number) {
  const [today, setToday] = useState<Today | null>(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [reload, setReload] = useState(0)
  const generation = useRef(0)
  const busy = useRef(false)
  const latestRead = useRef(0)
  const retry = useCallback(() => setReload(value => value + 1), [])

  useEffect(() => {
    const version = ++generation.current
    busy.current = false
    setPending(null)
    setToday(null)
    setError('')
    if (!token) return
    const controller = new AbortController()
    async function load() {
      if (busy.current) return
      const read = ++latestRead.current
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
      try {
        const response = await fetch(`/api/today?timezone=${encodeURIComponent(timezone)}`, {
          headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        })
        if (!response.ok) throw new Error()
        const data = await response.json()
        if (typeof data.date !== 'string' || typeof data.timezone !== 'string'
          || !Array.isArray(data.completed_ids) || !data.completed_ids.every((id: unknown) => typeof id === 'string')) throw new Error()
        if (!Array.isArray(data.history) || data.history.length !== 7 || !data.history.every((day: HistoryDay) =>
          typeof day.date === 'string' && Number.isInteger(day.total) && day.total >= 0 && Array.isArray(day.completed_ids) && day.completed_ids.every(id => typeof id === 'string'))) throw new Error()
        if (generation.current === version && latestRead.current === read) {
          setToday(data)
          setError('')
        }
      } catch {
        if (!controller.signal.aborted && generation.current === version && latestRead.current === read) {
          setToday(null)
          setError('Could not load today’s progress. Please retry.')
        }
      }
    }
    void load()
    const interval = window.setInterval(() => { if (!document.hidden) void load() }, 30000)
    const visible = () => { if (!document.hidden) void load() }
    window.addEventListener('focus', visible)
    document.addEventListener('visibilitychange', visible)
    return () => {
      generation.current++
      controller.abort()
      window.clearInterval(interval)
      window.removeEventListener('focus', visible)
      document.removeEventListener('visibilitychange', visible)
    }
  }, [token, refresh, reload])

  async function toggle(id: string) {
    if (!token || !today || busy.current) return
    const version = generation.current
    const completed = !today.completed_ids.includes(id)
    busy.current = true
    latestRead.current++ // An older read must not overwrite this check-in.
    setPending(id)
    setError('')
    try {
      const response = await fetch(`/api/habits/${id}/check-in`, {
        method: 'PUT', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: today.date, timezone: today.timezone, completed }),
        signal: AbortSignal.timeout(10000),
      })
      if (!response.ok) throw new Error(response.status === 409 ? 'day-changed' : 'save-failed')
      if (generation.current === version) {
        setToday(current => current && ({ ...current,
          history: current.history.map(day => day.date === today.date ? { ...day, completed_ids: completed
            ? [...new Set([...day.completed_ids, id])] : day.completed_ids.filter(value => value !== id) } : day),
          completed_ids: completed
          ? [...new Set([...current.completed_ids, id])]
          : current.completed_ids.filter(value => value !== id) }))
      }
    } catch (cause) {
      if (generation.current === version) {
        setToday(null)
        setError(cause instanceof Error && cause.message === 'day-changed'
          ? 'The day has changed. Reload today’s progress to continue.'
          : 'Could not confirm that check-in. Reload today’s progress before trying again.')
      }
    } finally {
      if (generation.current === version) { busy.current = false; setPending(null) }
    }
  }

  return { today, error, pending, retry, toggle }
}
