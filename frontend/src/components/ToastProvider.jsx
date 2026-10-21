import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Button from './Button'
import { ToastContext } from '../context/toastContext'

export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    const timer = timers.current.get(id)
    if (timer) window.clearTimeout(timer)
    timers.current.delete(id)
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const addToast = useCallback((message, variant = 'success', duration = 4500) => {
    const id = nextId.current++
    setToasts((current) => [...current, { id, message, variant }])
    if (duration > 0) {
      timers.current.set(id, window.setTimeout(() => dismiss(id), duration))
    }
    return id
  }, [dismiss])

  useEffect(() => () => {
    timers.current.forEach((timer) => window.clearTimeout(timer))
    timers.current.clear()
  }, [])

  const toast = useMemo(() => ({
    show: addToast,
    success: (message, duration) => addToast(message, 'success', duration),
    error: (message, duration) => addToast(message, 'error', duration),
    warning: (message, duration) => addToast(message, 'warning', duration),
    info: (message, duration) => addToast(message, 'info', duration),
    dismiss,
  }), [addToast, dismiss])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-viewport" aria-live="polite" aria-relevant="additions">
        {toasts.map((item) => (
          <div
            key={item.id}
            className={`toast toast-${item.variant}`}
            role={item.variant === 'error' ? 'alert' : 'status'}
          >
            <span>{item.message}</span>
            <Button
              variant="ghost"
              size="small"
              onClick={() => dismiss(item.id)}
              aria-label="Fermer la notification"
            >
              ×
            </Button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
