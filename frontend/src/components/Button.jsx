export default function Button({
  children,
  variant = 'primary',
  size = 'medium',
  loading = false,
  disabled = false,
  className = '',
  type = 'button',
  ...props
}) {
  const classes = ['button', `button-${variant}`, `button-${size}`, className]
    .filter(Boolean)
    .join(' ')

  return (
    <button
      {...props}
      className={classes}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && <span className="button-spinner" aria-hidden="true" />}
      {children}
    </button>
  )
}
