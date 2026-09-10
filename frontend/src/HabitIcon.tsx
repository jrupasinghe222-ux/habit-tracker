/** Lightweight decorative icons selected locally from the habit name. */
export function HabitIcon({ name }: { name: string }) {
  const text = name.toLocaleLowerCase()
  let shape
  if (/\b(meditat\w*|mindful\w*|yoga|breath\w*)\b/.test(text)) {
    shape = <><circle cx="12" cy="5" r="2" /><path d="M8 11c1-1 2-2 4-2s3 1 4 2M8 11l-2 4H3m13-4 2 4h3M10 12v4l-5 3c-1 .7-.5 2 1 2h12c1.5 0 2-1.3 1-2l-5-3v-4M9 21l3-2 3 2" /></>
  } else if (/\b(study|studying|read\w*|book\w*|learn\w*|revision|revise)\b/.test(text)) {
    shape = <><path d="M12 6C9 3 5 3 2 4v15c4-1 7 0 10 2 3-2 6-3 10-2V4c-3-1-7-1-10 2Zm0 0v15M5 8c1.5 0 3 .4 4 1M15 9c1-.6 2.5-1 4-1M5 12c1.5 0 3 .4 4 1M15 13c1-.6 2.5-1 4-1" /></>
  } else if (/\b(cat\w*|dog\w*|pet\w*|feed\w*)\b/.test(text)) {
    shape = <><ellipse cx="5" cy="9" rx="2" ry="2.5" /><ellipse cx="10" cy="5" rx="2" ry="2.5" /><ellipse cx="16" cy="5" rx="2" ry="2.5" /><ellipse cx="21" cy="10" rx="2" ry="2.5" /><path d="M7 16c2-1 2-5 5-5s3 4 5 5c3 3 0 6-3 4-1-.6-3-.6-4 0-3 2-6-1-3-4Z" /></>
  } else if (/\b(water|hydrat\w*|drink\w*)\b/.test(text)) {
    shape = <><path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z" /><path d="M9 16a3 3 0 0 0 3 3" /></>
  } else if (/\b(sleep\w*|bed\w*|rest\w*)\b/.test(text)) {
    shape = <path d="M20.5 14A9 9 0 0 1 10 3a9 9 0 1 0 10.5 11Z" />
  } else if (/\b(exercis\w*|workout\w*|gym|lift\w*|fitness|run\w*|walk\w*)\b/.test(text)) {
    shape = <><path d="M7 12h10M2 10v4m20-4v4" /><rect x="3" y="7" width="4" height="10" rx="1" /><rect x="17" y="7" width="4" height="10" rx="1" /></>
  } else if (/\b(code|coding|program\w*)\b/.test(text)) {
    shape = <path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16" />
  } else if (/\b(music|piano|guitar|sing\w*)\b/.test(text)) {
    shape = <><path d="M9 18V5l12-2v13M9 9l12-2" /><ellipse cx="6" cy="18" rx="3" ry="2.5" /><ellipse cx="18" cy="16" rx="3" ry="2.5" /></>
  } else if (/\b(writ\w*|journal\w*|draw\w*)\b/.test(text)) {
    shape = <><path d="m15 5 4 4M4 20l5-1L21 7a2.8 2.8 0 0 0-4-4L5 15l-1 5ZM4 20h16" /></>
  } else {
    shape = <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="4" /><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" /></>
  }
  return <svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{shape}</svg>
}
