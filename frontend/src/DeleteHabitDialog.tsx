import { useEffect, useRef } from 'react'

type Props = {
  dateLabel?: string
  name: string
  busy: boolean
  error: string
  onCancel: () => void
  onConfirm: () => void
}

export function DeleteHabitDialog({ name, dateLabel, busy, error, onCancel, onConfirm }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const cancel = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const element = dialog.current!
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    element.showModal()
    cancel.current?.focus()
    return () => {
      element.close()
      if (previousFocus?.isConnected) previousFocus.focus()
      else document.getElementById('habit-name')?.focus()
    }
  }, [])

  return (
    <dialog ref={dialog} className="delete-dialog" aria-labelledby="delete-title"
      aria-describedby="delete-description" aria-busy={busy}
      onCancel={event => { event.preventDefault(); if (!busy) onCancel() }}>
      <div className="delete-dialog-heading">
      <div className="delete-dialog-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6m4-6v6" />
        </svg>
      </div>
      <h2 id="delete-title">Delete this task?</h2>
      </div>
      <p id="delete-description"><strong>{name}</strong> will be deleted{dateLabel ? ` from ${dateLabel} only` : ''}. This can't be undone.</p>
      {error && <p className="dialog-error" role="alert">{error}</p>}
      <div className="dialog-actions">
        <button ref={cancel} type="button" className="secondary" disabled={busy} onClick={onCancel}>Cancel</button>
        <button type="button" className="danger-button" disabled={busy} onClick={onConfirm}>
          {busy ? 'Deleting…' : 'Delete task'}
        </button>
      </div>
    </dialog>
  )
}
