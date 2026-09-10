import { useState } from 'react'
import type { HistoryDay } from './useDailyProgress'

type Props = { days: HistoryDay[]; habits: { id: string; name: string }[] }

function displayDate(day: string, options: Intl.DateTimeFormatOptions) {
  // A stored calendar date must not move to the previous day in a western timezone.
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`))
}

export function WeeklyProgress({ days, habits }: Props) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const selected = days.find(day => day.date === selectedDate) ?? days[days.length - 1]
  const visible = new Set(habits.map(habit => habit.id))
  const counts = days.map(day => day.completed_ids.filter(id => visible.has(id)).length)
  const total = counts.reduce((sum, count) => sum + count, 0)
  const activeDays = counts.filter(count => count > 0).length
  const selectedHabits = habits.filter(habit => selected.completed_ids.includes(habit.id))

  return <section className="weekly-progress" aria-labelledby="weekly-title">
    <div className="weekly-heading"><div><h2 id="weekly-title">Your last 7 days</h2>
      <span className="weekly-summary">{total} {total === 1 ? 'check-in' : 'check-ins'} · {activeDays} active {activeDays === 1 ? 'day' : 'days'}</span>
    </div><span className="weekly-range">{displayDate(days[0].date, { month: 'short', day: 'numeric' })} – {displayDate(days[6].date, { month: 'short', day: 'numeric' })}</span></div>
    <div className="week-chart" role="group" aria-label="Select a day to see completed habits">
      {days.map((day, index) => <button key={day.date} type="button" className={`week-day${selected.date === day.date ? ' selected' : ''}`}
        aria-pressed={selected.date === day.date}
        aria-label={`${displayDate(day.date, { dateStyle: 'full' })}: ${counts[index]} of ${day.total} tasks completed`}
        onClick={() => setSelectedDate(day.date)}>
        <span className="day-count">{counts[index]}/{day.total}</span>
        <span className="day-track" aria-hidden="true"><span style={{ height: `${day.total ? Math.min(counts[index] / day.total * 100, 100) : 0}%` }} /></span>
        <span className="day-label">{index === 6 ? 'Today' : displayDate(day.date, { weekday: 'short' })}</span>
      </button>)}
    </div>
    <div className="history-detail" aria-live="polite">
      <h3>{displayDate(selected.date, { weekday: 'long', month: 'short', day: 'numeric' })}</h3>
      {selectedHabits.length ? <ul>{selectedHabits.map(habit => <li key={habit.id}><span aria-hidden="true">✓</span> {habit.name}</li>)}</ul>
        : <p>No check-ins recorded for this day.</p>}
    </div>
    <p className="history-note">History for the habits in your current list. Select a day to explore.</p>
  </section>
}
