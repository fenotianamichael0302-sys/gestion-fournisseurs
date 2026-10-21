import { useId } from 'react'

export function FormField({
  label,
  name,
  value,
  onChange,
  type = 'text',
  required = false,
  ...inputProps
}) {
  const id = useId()
  return (
    <label className="form-field" htmlFor={id}>
      <span>{label}</span>
      <input
        {...inputProps}
        id={id}
        name={name}
        type={type}
        value={value ?? ''}
        onChange={onChange}
        required={required}
      />
    </label>
  )
}

export function SelectField({ label, name, value, onChange, options, required = false, ...selectProps }) {
  const id = useId()
  return (
    <label className="form-field" htmlFor={id}>
      <span>{label}</span>
      <select {...selectProps} id={id} name={name} value={value ?? ''} onChange={onChange} required={required}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  )
}

export function TextAreaField({ label, name, value, onChange, rows = 3 }) {
  const id = useId()
  return (
    <label className="form-field form-field-wide" htmlFor={id}>
      <span>{label}</span>
      <textarea id={id} name={name} rows={rows} value={value ?? ''} onChange={onChange} />
    </label>
  )
}
