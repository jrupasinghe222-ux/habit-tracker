type Day = { date: string; total: number; completed_ids: string[] }
type Props = { days: Day[]; selectedDate: string; today: string; disabled: boolean; onSelect: (day: string) => void }
function displayDate(day: string, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(new Date(`${day}T12:00:00Z`))
}
export function WeeklyProgress({ days, selectedDate, today, disabled, onSelect }: Props) {
  const counts = days.map(day => day.completed_ids.length)
  const total = counts.reduce((sum, count) => sum + count, 0)
  const activeDays = counts.filter(count => count > 0).length
  return <section className="weekly-progress" aria-labelledby="weekly-title">
    <div className="weekly-heading"><div><h2 id="weekly-title">Your last 7 days</h2>
      <span className="weekly-summary">{total} {total === 1 ? 'check-in' : 'check-ins'} · {activeDays} active {activeDays === 1 ? 'day' : 'days'}</span></div>
      <span className="weekly-range">{displayDate(days[0].date, { month: 'short', day: 'numeric' })} – {displayDate(days[6].date, { month: 'short', day: 'numeric' })}</span></div>
    <div className="week-chart" role="group" aria-label="Select a day to view and edit its tasks">
      {days.map((day, index) => <button key={day.date} type="button" disabled={disabled || day.date < '2000-01-01'}
        className={`week-day${selectedDate === day.date ? ' selected' : ''}`} aria-pressed={selectedDate === day.date}
        aria-label={`${displayDate(day.date, { dateStyle: 'full' })}: ${counts[index]} of ${day.total} tasks completed`} onClick={() => onSelect(day.date)}>
        <span className="day-count">{counts[index]}/{day.total}</span>
        <span className="day-track" aria-hidden="true"><span style={{ height: `${day.total ? Math.min(counts[index] / day.total * 100, 100) : 0}%` }} /></span>
        <span className="day-label">{day.date === today ? 'Today' : displayDate(day.date, { weekday: 'short' })}</span>
      </button>)}
    </div>
    <p className="history-note">Select a day to open its tasks above. Changes stay on that date.</p>
  </section>
}
