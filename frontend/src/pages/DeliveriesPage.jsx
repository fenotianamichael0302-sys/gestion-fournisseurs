import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const orderStatuses = 'VALIDEE,EN_COURS_LIVRAISON,PARTIELLEMENT_LIVREE'

function localDate() {
  return new Date(Date.now() - new Date().getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 10)
}

function emptyForm() {
  return { order: '', delivery_date: localDate(), notes: '', lines: [] }
}

export default function DeliveriesPage() {
  const toast = useToast()
  const [form, setForm] = useState(emptyForm)
  const [isOpen, setIsOpen] = useState(false)
  const [formError, setFormError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const orders = useApiList('orders', { status: orderStatuses })
  const deliveries = useApiList('deliveries')
  const selectedOrder = orders.rows.find((order) => String(order.id) === form.order)

  function openCreate() {
    setForm(emptyForm())
    setFormError('')
    setIsOpen(true)
  }

  function updateField(event) {
    const { name, value } = event.target
    setForm((current) => ({
      ...current,
      [name]: value,
      ...(name === 'order'
        ? {
            lines: orders.rows
              .find((order) => String(order.id) === value)
              ?.lines.map((line) => ({
                order_line: line.id,
                product_name: line.product_name,
                quantity_ordered: line.quantity,
                quantity_received: '',
                quantity_damaged: '0',
                quantity_missing: '0',
                notes: '',
              })) || [],
          }
        : {}),
    }))
  }

  function updateLine(index, event) {
    const { name, value } = event.target
    setForm((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => (
        lineIndex === index ? { ...line, [name]: value } : line
      )),
    }))
  }

  async function saveDelivery(event) {
    event.preventDefault()
    setIsSaving(true)
    setFormError('')
    const lines = form.lines
      .filter((line) => Number(line.quantity_received) > 0)
      .map(({ order_line, quantity_received, quantity_damaged, quantity_missing, notes }) => ({
        order_line,
        quantity_received,
        quantity_damaged,
        quantity_missing,
        notes,
      }))
    try {
      await api.post('/deliveries/', {
        order: Number(form.order),
        delivery_date: form.delivery_date,
        notes: form.notes,
        lines,
      })
      toast.success('Réception de livraison enregistrée.')
      setIsOpen(false)
      deliveries.refresh()
      orders.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  const columns = [
    { key: 'order_number', header: 'Commande' },
    { key: 'supplier_name', header: 'Fournisseur' },
    { key: 'delivery_date', header: 'Date de réception', sortable: true },
    {
      key: 'lines',
      header: 'Quantités et anomalies',
      render: (lines) => (
        <ul className="delivery-line-summary">
          {lines.map((line) => (
            <li key={line.id}>
              {line.product_name} : {line.quantity_received} reçue(s)
              {Number(line.quantity_damaged) > 0 && `, ${line.quantity_damaged} endommagée(s)`}
              {Number(line.quantity_missing) > 0 && `, ${line.quantity_missing} manquante(s)`}
              {line.notes && ` — ${line.notes}`}
            </li>
          ))}
        </ul>
      ),
    },
    { key: 'created_by_username', header: 'Enregistrée par' },
  ]

  return (
    <section>
      <PageHeader
        title="Suivi des livraisons"
        description="Enregistrez les réceptions réelles, y compris les quantités endommagées ou manquantes."
        actions={<Button onClick={openCreate}>Enregistrer une réception</Button>}
      />
      {deliveries.error && <p className="inline-alert" role="alert">{deliveries.error}</p>}
      <DataTable
        columns={columns}
        rows={deliveries.rows}
        loading={deliveries.isLoading}
        page={deliveries.page}
        pageSize={25}
        totalItems={deliveries.count}
        onPageChange={deliveries.setPage}
        emptyMessage="Aucune réception enregistrée."
      />
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Nouvelle réception"
        description="La commande ne sera marquée comme livrée que lorsque toutes les quantités commandées auront été reçues sans dommage."
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsOpen(false)}>Annuler</Button>
            <Button type="submit" form="delivery-form" loading={isSaving}>Enregistrer</Button>
          </>
        )}
      >
        <form id="delivery-form" onSubmit={saveDelivery}>
          <div className="form-grid">
            <SelectField
              label="Commande validée"
              name="order"
              value={form.order}
              onChange={updateField}
              required
              options={[
                { value: '', label: orders.isLoading ? 'Chargement…' : 'Sélectionner une commande' },
                ...orders.rows.map((order) => ({
                  value: String(order.id),
                  label: `${order.order_number} — ${order.supplier_name}`,
                })),
              ]}
            />
            <FormField
              label="Date de réception"
              name="delivery_date"
              type="date"
              value={form.delivery_date}
              onChange={updateField}
              required
            />
            <TextAreaField label="Observations générales" name="notes" value={form.notes} onChange={updateField} />
          </div>
          {selectedOrder && (
            <div className="line-items">
              <h3>Articles de la commande</h3>
              {form.lines.map((line, index) => (
                <div className="line-item-row" key={line.order_line}>
                  <strong>{line.product_name} ({line.quantity_ordered} commandée(s))</strong>
                  <FormField
                    label="Reçue"
                    name="quantity_received"
                    type="number"
                    min="0.001"
                    step="0.001"
                    value={line.quantity_received}
                    onChange={(event) => updateLine(index, event)}
                  />
                  <FormField
                    label="Endommagée"
                    name="quantity_damaged"
                    type="number"
                    min="0"
                    step="0.001"
                    value={line.quantity_damaged}
                    onChange={(event) => updateLine(index, event)}
                  />
                  <FormField
                    label="Manquante signalée"
                    name="quantity_missing"
                    type="number"
                    min="0"
                    step="0.001"
                    value={line.quantity_missing}
                    onChange={(event) => updateLine(index, event)}
                  />
                  <FormField
                    label="Observation"
                    name="notes"
                    value={line.notes}
                    onChange={(event) => updateLine(index, event)}
                  />
                </div>
              ))}
            </div>
          )}
          {formError && <p className="form-error" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
