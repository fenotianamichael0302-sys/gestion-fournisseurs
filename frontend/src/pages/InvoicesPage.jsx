import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const invoiceStatuses = {
  NON_PAYEE: 'Non payée',
  PARTIELLEMENT_PAYEE: 'Partiellement payée',
  PAYEE: 'Payée',
  EN_RETARD: 'En retard',
}
const emptyLine = () => ({ product_name: '', quantity: '1', unit_price: '0.00', tax_rate: '0.00' })
const emptyInvoice = () => ({
  supplier: '',
  order: '',
  invoice_number: '',
  invoice_date: '',
  due_date: '',
  notes: '',
  lines: [emptyLine()],
})

function amount(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

export default function InvoicesPage() {
  const toast = useToast()
  const [status, setStatus] = useState('')
  const invoices = useApiList('invoices', status ? { status } : {})
  const suppliers = useApiList('suppliers')
  const orders = useApiList('orders')
  const [form, setForm] = useState(emptyInvoice)
  const [editing, setEditing] = useState(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [formError, setFormError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  function startCreate() {
    setEditing(null)
    setForm(emptyInvoice())
    setFormError('')
    setIsFormOpen(true)
  }

  function startEdit(invoice) {
    setEditing(invoice)
    setForm({
      supplier: String(invoice.supplier),
      order: invoice.order ? String(invoice.order) : '',
      invoice_number: invoice.invoice_number,
      invoice_date: invoice.invoice_date,
      due_date: invoice.due_date,
      notes: invoice.notes || '',
      lines: invoice.lines.map(({ product_name, quantity, unit_price, tax_rate }) => ({
        product_name,
        quantity: String(quantity),
        unit_price: String(unit_price),
        tax_rate: String(tax_rate),
      })),
    })
    setFormError('')
    setIsFormOpen(true)
  }

  function changeField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
      ...(event.target.name === 'supplier' ? { order: '' } : {}),
    }))
  }

  function changeLine(index, event) {
    const { name, value } = event.target
    setForm((current) => ({
      ...current,
      lines: current.lines.map((line, lineIndex) => (
        lineIndex === index ? { ...line, [name]: value } : line
      )),
    }))
  }

  async function saveInvoice(event) {
    event.preventDefault()
    setIsSaving(true)
    setFormError('')
    const payload = editing?.amount_paid > 0
      ? { due_date: form.due_date, notes: form.notes }
      : {
          supplier: Number(form.supplier),
          order: form.order ? Number(form.order) : null,
          invoice_number: form.invoice_number,
          invoice_date: form.invoice_date,
          due_date: form.due_date,
          notes: form.notes,
          lines: form.lines,
        }
    try {
      if (editing) await api.patch(`/invoices/${editing.id}/`, payload)
      else await api.post('/invoices/', payload)
      toast.success(editing ? 'Facture modifiée.' : 'Facture enregistrée.')
      setIsFormOpen(false)
      invoices.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  const columns = [
    { key: 'invoice_number', header: 'N° facture', sortable: true },
    { key: 'supplier_name', header: 'Fournisseur', sortable: true },
    { key: 'invoice_date', header: 'Date facture', sortable: true },
    { key: 'due_date', header: 'Échéance', sortable: true },
    { key: 'total_ttc', header: 'Total TTC', sortable: true, render: (value) => amount(value) },
    { key: 'balance_due', header: 'Reste à payer', sortable: true, render: (value) => amount(value) },
    {
      key: 'status',
      header: 'Statut',
      render: (value) => <span className={`status-badge status-${value.toLowerCase()}`}>{invoiceStatuses[value]}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (_value, invoice) => (
        <Button variant="ghost" size="small" onClick={() => startEdit(invoice)}>Voir / modifier</Button>
      ),
    },
  ]

  const total = form.lines.reduce((sum, line) => {
    const net = Number(line.quantity || 0) * Number(line.unit_price || 0)
    return sum + net + (net * Number(line.tax_rate || 0) / 100)
  }, 0)
  const hasPayments = Number(editing?.amount_paid || 0) > 0

  return (
    <section>
      <PageHeader
        title="Factures fournisseurs"
        description="Suivez les échéances, les montants dus et les règlements reçus."
        actions={<Button onClick={startCreate}>Enregistrer une facture</Button>}
      />
      {invoices.error && <p className="inline-alert" role="alert">{invoices.error}</p>}
      <div className="list-filter">
        <label className="form-field compact-field">
          <span>Statut</span>
          <select value={status} onChange={(event) => { setStatus(event.target.value); invoices.setPage(1) }}>
            <option value="">Tous les statuts</option>
            {Object.entries(invoiceStatuses).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>
      <DataTable
        columns={columns}
        rows={invoices.rows}
        loading={invoices.isLoading}
        page={invoices.page}
        pageSize={25}
        totalItems={invoices.count}
        onPageChange={invoices.setPage}
        searchValue={invoices.search}
        onSearchChange={invoices.setSearch}
        searchLabel="Rechercher une facture"
        emptyMessage="Aucune facture trouvée."
      />
      <Modal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        title={editing ? `Facture ${editing.invoice_number}` : 'Nouvelle facture'}
        description={hasPayments ? 'Une facture réglée partiellement ne peut plus changer de lignes ou de fournisseur.' : 'Les montants HT, taxes et TTC sont calculés automatiquement.'}
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsFormOpen(false)}>Annuler</Button>
            <Button type="submit" form="invoice-form" loading={isSaving}>Enregistrer</Button>
          </>
        )}
      >
        <form id="invoice-form" onSubmit={saveInvoice}>
          <div className="form-grid">
            <SelectField
              label="Fournisseur"
              name="supplier"
              value={form.supplier}
              onChange={changeField}
              required
              options={[
                { value: '', label: 'Sélectionner un fournisseur' },
                ...suppliers.rows.map((supplier) => ({ value: String(supplier.id), label: supplier.company_name })),
              ]}
              disabled={hasPayments}
            />
            <SelectField
              label="Commande associée"
              name="order"
              value={form.order}
              onChange={changeField}
              options={[
                { value: '', label: 'Aucune commande' },
                ...orders.rows
                  .filter((order) => String(order.supplier) === form.supplier)
                  .map((order) => ({ value: String(order.id), label: order.order_number })),
              ]}
              disabled={hasPayments}
            />
            <FormField label="Numéro de facture" name="invoice_number" value={form.invoice_number} onChange={changeField} required disabled={hasPayments} />
            <FormField label="Date de facture" name="invoice_date" type="date" value={form.invoice_date} onChange={changeField} required disabled={hasPayments} />
            <FormField label="Date d'échéance" name="due_date" type="date" value={form.due_date} onChange={changeField} required />
            <TextAreaField label="Notes" name="notes" value={form.notes} onChange={changeField} />
          </div>
          {!hasPayments && (
            <>
              <div className="line-items-heading">
                <h3>Articles facturés</h3>
                <Button variant="secondary" size="small" onClick={() => setForm((current) => ({ ...current, lines: [...current.lines, emptyLine()] }))}>
                  Ajouter une ligne
                </Button>
              </div>
              <div className="line-items">
                {form.lines.map((line, index) => (
                  <div className="line-item-row" key={index}>
                    <FormField label="Désignation" name="product_name" value={line.product_name} onChange={(event) => changeLine(index, event)} required />
                    <FormField label="Quantité" name="quantity" type="number" min="0.001" step="0.001" value={line.quantity} onChange={(event) => changeLine(index, event)} required />
                    <FormField label="Prix unitaire HT" name="unit_price" type="number" min="0" step="0.01" value={line.unit_price} onChange={(event) => changeLine(index, event)} required />
                    <FormField label="Taxe (%)" name="tax_rate" type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={(event) => changeLine(index, event)} />
                    <Button variant="ghost" size="small" onClick={() => setForm((current) => ({
                      ...current,
                      lines: current.lines.length > 1
                        ? current.lines.filter((_item, lineIndex) => lineIndex !== index)
                        : current.lines,
                    }))} aria-label={`Supprimer la ligne ${index + 1}`}>×</Button>
                  </div>
                ))}
              </div>
              <p className="form-total">Total TTC estimé : <strong>{amount(total)}</strong></p>
            </>
          )}
          {formError && <p className="form-error" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
