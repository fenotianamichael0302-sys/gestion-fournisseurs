import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const paymentMethods = {
  VIREMENT: 'Virement',
  CHEQUE: 'Chèque',
  ESPECES: 'Espèces',
  MOBILE_MONEY: 'Mobile money',
  CARTE: 'Carte',
}
const blankPayment = () => ({
  invoice: '',
  payment_date: new Date().toISOString().slice(0, 10),
  amount: '',
  method: 'VIREMENT',
  reference: '',
  notes: '',
})

function amount(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

export default function PaymentsPage() {
  const toast = useToast()
  const payments = useApiList('payments')
  const invoices = useApiList('invoices')
  const [form, setForm] = useState(blankPayment)
  const [editing, setEditing] = useState(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [formError, setFormError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  function openCreate() {
    setEditing(null)
    setForm(blankPayment())
    setFormError('')
    setIsFormOpen(true)
  }

  function openEdit(payment) {
    setEditing(payment)
    setForm({
      invoice: String(payment.invoice),
      payment_date: payment.payment_date,
      amount: String(payment.amount),
      method: payment.method,
      reference: payment.reference || '',
      notes: payment.notes || '',
    })
    setFormError('')
    setIsFormOpen(true)
  }

  function changeField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function savePayment(event) {
    event.preventDefault()
    setIsSaving(true)
    setFormError('')
    const payload = {
      ...form,
      invoice: Number(form.invoice),
      amount: Number(form.amount),
    }
    try {
      if (editing) await api.patch(`/payments/${editing.id}/`, payload)
      else await api.post('/payments/', payload)
      toast.success(editing ? 'Paiement modifié.' : 'Paiement enregistré.')
      setIsFormOpen(false)
      payments.refresh()
      invoices.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  const selectedInvoice = invoices.rows.find((invoice) => String(invoice.id) === form.invoice)
  const availableInvoices = invoices.rows.filter((invoice) => {
    if (invoice.status !== 'PAYEE') return true
    return editing && String(invoice.id) === form.invoice
  })
  const maxAmount = selectedInvoice
    ? Number(selectedInvoice.balance_due) + (editing && editing.invoice === selectedInvoice.id ? Number(editing.amount) : 0)
    : undefined
  const columns = [
    { key: 'payment_date', header: 'Date', sortable: true },
    { key: 'invoice_number', header: 'Facture', sortable: true },
    { key: 'supplier_name', header: 'Fournisseur', sortable: true },
    { key: 'amount', header: 'Montant', sortable: true, render: (value) => amount(value) },
    { key: 'method', header: 'Mode', render: (value) => paymentMethods[value] || value },
    { key: 'reference', header: 'Référence' },
    {
      key: 'actions',
      header: 'Actions',
      render: (_value, payment) => (
        <Button variant="ghost" size="small" onClick={() => openEdit(payment)}>Voir / modifier</Button>
      ),
    },
  ]

  return (
    <section>
      <PageHeader
        title="Paiements"
        description="Enregistrez les règlements partiels ou complets sans dépasser le solde dû."
        actions={<Button onClick={openCreate}>Enregistrer un paiement</Button>}
      />
      {payments.error && <p className="inline-alert" role="alert">{payments.error}</p>}
      <DataTable
        columns={columns}
        rows={payments.rows}
        loading={payments.isLoading}
        page={payments.page}
        pageSize={25}
        totalItems={payments.count}
        onPageChange={payments.setPage}
        searchValue={payments.search}
        onSearchChange={payments.setSearch}
        searchLabel="Rechercher un paiement"
        emptyMessage="Aucun paiement enregistré."
      />
      <Modal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        title={editing ? 'Modifier le paiement' : 'Nouveau paiement'}
        description="Le serveur vérifie le solde restant et refuse les paiements excédentaires."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsFormOpen(false)}>Annuler</Button>
            <Button type="submit" form="payment-form" loading={isSaving}>Enregistrer</Button>
          </>
        )}
      >
        <form id="payment-form" className="form-grid" onSubmit={savePayment}>
          <SelectField
            label="Facture"
            name="invoice"
            value={form.invoice}
            onChange={changeField}
            required
            options={[
              { value: '', label: 'Sélectionner une facture' },
              ...availableInvoices.map((invoice) => ({
                value: String(invoice.id),
                label: `${invoice.invoice_number} — ${invoice.supplier_name} (reste ${amount(invoice.balance_due)})`,
              })),
            ]}
          />
          <FormField
            label="Date de paiement"
            name="payment_date"
            type="date"
            value={form.payment_date}
            onChange={changeField}
            required
          />
          <FormField
            label="Montant"
            name="amount"
            type="number"
            min="0.01"
            max={maxAmount}
            step="0.01"
            value={form.amount}
            onChange={changeField}
            required
          />
          <SelectField
            label="Mode de paiement"
            name="method"
            value={form.method}
            onChange={changeField}
            required
            options={Object.entries(paymentMethods).map(([value, label]) => ({ value, label }))}
          />
          <FormField label="Référence" name="reference" value={form.reference} onChange={changeField} required={!editing} />
          <TextAreaField label="Notes" name="notes" value={form.notes} onChange={changeField} />
          {selectedInvoice && (
            <p className="form-field-wide">Solde courant : <strong>{amount(maxAmount)}</strong></p>
          )}
          {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
