import { useEffect, useId, useRef } from 'react'
import { createPortal } from 'react-dom'
import Button from './Button'

export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'medium',
}) {
  const dialogRef = useRef(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (isOpen && !dialog.open) dialog.showModal()
    if (!isOpen && dialog.open) dialog.close()
  }, [isOpen])

  if (!isOpen) return null

  return createPortal(
    <dialog
      ref={dialogRef}
      className={`modal modal-${size}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault()
        onClose()
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div className="modal-header">
        <div>
          <h2 id={titleId}>{title}</h2>
          {description && <p id={descriptionId}>{description}</p>}
        </div>
        <Button variant="ghost" size="small" onClick={onClose} aria-label="Fermer la fenêtre">
          ×
        </Button>
      </div>
      <div className="modal-body">{children}</div>
      {footer && <div className="modal-footer">{footer}</div>}
    </dialog>,
    document.body,
  )
}
