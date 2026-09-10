import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { HabitIcon } from './HabitIcon'

type Habit = { id: string; name: string }
type Props = {
  habit: Habit
  completed: boolean
  checkingIn: boolean
  checkInDisabled: boolean
  onCheckIn: () => void
  deleting: boolean
  deleteBusy: boolean
  onSave: (id: string, name: string) => Promise<boolean>
  onDelete: () => void
}

export function HabitCard({ habit, completed, checkingIn, checkInDisabled, onCheckIn, deleting, deleteBusy, onSave, onDelete }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(habit.name)
  const [saving, setSaving] = useState(false)
  const editButton = useRef<HTMLButtonElement>(null)
  const restoreFocus = useRef(false)

  useEffect(() => {
    if (!editing && restoreFocus.current) {
      editButton.current?.focus()
      restoreFocus.current = false
    }
  }, [editing])

  function cancel() {
    if (saving) return
    setDraft(habit.name)
    restoreFocus.current = true
    setEditing(false)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (saving || !draft.trim() || draft.trim() === habit.name) return
    setSaving(true)
    try {
      if (await onSave(habit.id, draft.trim())) {
        restoreFocus.current = true
        setEditing(false)
      }
    } finally { setSaving(false) }
  }

  return (
    <li className={`habit-card${editing ? ' is-editing' : ''}${completed ? ' is-complete' : ''}`}>
      <div className="habit-emblem" aria-hidden="true"><HabitIcon name={habit.name} /></div>
      {editing ? (
        <form className="habit-editor" onSubmit={event => void save(event)}
          onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancel() } }}>
          <label htmlFor={`edit-${habit.id}`}>Edit habit</label>
          <input id={`edit-${habit.id}`} value={draft} autoFocus maxLength={80} required
            disabled={saving} onChange={event => setDraft(event.target.value)} />
          <div className="habit-actions">
            <button disabled={saving || !draft.trim() || draft.trim() === habit.name}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
            <button type="button" className="secondary" disabled={saving} onClick={cancel}>Cancel</button>
          </div>
        </form>
      ) : (
        <>
          <div className="habit-copy">

            <h3>{habit.name}</h3>
          </div>
          <div className="habit-actions">
            <button type="button" className={`check-in${completed ? ' checked-in' : ''}`}
              aria-pressed={completed} aria-label={`${completed ? 'Undo today check-in for' : 'Mark done today:'} ${habit.name}`}
              disabled={checkInDisabled || deleting} onClick={onCheckIn}>
              {checkingIn ? 'Saving…' : completed ? '✓ Done today' : 'Done today'}
            </button>
            <button ref={editButton} type="button" className="secondary edit-habit"
              disabled={deleting} aria-label={`Edit ${habit.name}`}
              onClick={() => { setDraft(habit.name); setEditing(true) }}>Edit</button>
            <button type="button" className="secondary delete-habit" disabled={deleteBusy}
              aria-label={`Delete ${habit.name}`} onClick={onDelete}>
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </>
      )}
    </li>
  )
}
