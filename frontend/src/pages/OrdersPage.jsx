import { useMemo, useState } from 'react'
import { api, downloadFile, getErrorMessage } from '../api/client'
import { useToast } from '../context/useToast'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import useApiList from '../hooks/useApiList'
import { useAuth } from '../context/useAuth'

const statuses = [
  { value: 'BROUILLON', label: 'Brouillon' },
  { value: 'EN_ATTENTE', label: 'En attente' },
  { value: 'VALIDEE', label: 'Validée' },
  { value: 'REFUSEE', label: 'Refusée' },
  { value: 'EN_COURS_LIVRAISON', label: 'En cours de livraison' },
  { value: 'PARTIELLEMENT_LIVREE', label: 'Partiellement livrée' },
  { value: 'LIVREE', label: 'Livrée' },
  { value: 'ANNULEE', label: 'Annulée' },
]
const statusLabels = Object.fromEntries(statuses.map(({ value, label }) => [value, label]))
const emptyLine = () => ({ product_name: '', quantity: '1', unit_price: '0.00', tax_rate: '0.00' })
const emptyOrder = () => ({
  supplier: '',
  order_date: '',
  expected_delivery_date: '',
  terms: '',
  notes: '',
  lines: [emptyLine()],
})

function formatAmount(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

export default function OrdersPage() {
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user.role === 'ADMINISTRATEUR'
  const [status, setStatus] = useState('')
  const query = useMemo(() => status ? { status } : {}, [status])
  const { rows, page, setPage, search, setSearch, count, isLoading, error, refresh } =
    useApiList('orders', query)
  const suppliers = useApiList('suppliers')
  const [form, setForm] = useState(emptyOrder)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [formError, setFormError] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [downloadingOrderId, setDownloadingOrderId] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [rejectionReason, setRejectionReason] = useState('')

  function startCreate() {
    setEditing(null)
    setForm(emptyOrder())
    setFormError('')
    setIsFormOpen(true)
  }

  function startEdit(order) {
    setEditing(order)
    setForm({
      supplier: String(order.supplier),
      order_date: order.order_date || '',
      expected_delivery_date: order.expected_delivery_date || '',
      terms: order.terms || '',
      notes: order.notes || '',
      lines: order.lines.map(({ product_name, quantity, unit_price, tax_rate }) => ({
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
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
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

  function addLine() {
    setForm((current) => ({ ...current, lines: [...current.lines, emptyLine()] }))
  }

  function removeLine(index) {
    setForm((current) => ({
      ...current,
      lines: current.lines.length > 1
        ? current.lines.filter((_line, lineIndex) => lineIndex !== index)
        : current.lines,
    }))
  }

  async function saveOrder(event) {
    event.preventDefault()
    setIsSaving(true)
    setFormError('')
    const payload = {
      supplier: Number(form.supplier),
      ...(form.order_date ? { order_date: form.order_date } : {}),
      expected_delivery_date: form.expected_delivery_date || null,
      terms: form.terms,
      notes: form.notes,
      lines: form.lines,
    }
    try {
      if (editing) await api.patch(`/orders/${editing.id}/`, payload)
      else await api.post('/orders/', payload)
      toast.success(editing ? 'Commande modifiée.' : 'Commande créée.')
      setIsFormOpen(false)
      refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  async function updateOrderAction(order, action, payload = {}) {
    try {
      await api.post(`/orders/${order.id}/${action}/`, payload)
      toast.success(action === 'submit' ? 'Commande soumise pour validation.' : 'Commande mise à jour.')
      refresh()
      setRejecting(null)
      setRejectionReason('')
    } catch (actionError) {
      toast.error(getErrorMessage(actionError))
    }
  }

  async function rejectOrder(event) {
    event.preventDefault()
    await updateOrderAction(rejecting, 'reject', { reason: rejectionReason })
  }

  async function downloadOrderPdf(order) {
    setDownloadingOrderId(order.id)
    try {
      await downloadFile(`/orders/${order.id}/pdf/`, `${order.order_number}.pdf`)
      toast.success('Bon de commande téléchargé.')
    } catch (downloadError) {
      toast.error(getErrorMessage(downloadError))
    } finally {
      setDownloadingOrderId(null)
    }
  }

  const columns = [
    { key: 'order_number', header: 'N° commande', sortable: true },
    { key: 'supplier_name', header: 'Fournisseur', sortable: true },
    { key: 'order_date', header: 'Date', sortable: true },
    {
      key: 'total_ttc',
      header: 'Total TTC',
      sortable: true,
      render: (value) => `${formatAmount(value)}`,
    },
    {
      key: 'status',
      header: 'Statut',
      render: (value) => <span className={`status-badge status-${value.toLowerCase()}`}>{statusLabels[value] || value}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (_value, order) => (
        <div className="table-actions">
          {order.status === 'BROUILLON' && (isAdmin || order.created_by === user.id) && (
            <Button variant="ghost" size="small" onClick={() => startEdit(order)}>Modifier</Button>
          )}
          <Button variant="secondary" size="small" loading={downloadingOrderId === order.id} disabled={downloadingOrderId !== null} onClick={() => downloadOrderPdf(order)}>
            Télécharger PDF
          </Button>
          {order.status === 'BROUILLON' && order.created_by === user.id && (
            <Button size="small" onClick={() => updateOrderAction(order, 'submit')}>Soumettre</Button>
          )}
          {isAdmin && order.status === 'EN_ATTENTE' && order.created_by !== user.id && (
            <>
              <Button size="small" onClick={() => updateOrderAction(order, 'approve')}>Valider</Button>
              <Button variant="danger" size="small" onClick={() => { setRejecting(order); setRejectionReason('') }}>Refuser</Button>
            </>
          )}
          {['BROUILLON', 'EN_ATTENTE'].includes(order.status) && (isAdmin || order.created_by === user.id) && (
            <Button variant="ghost" size="small" onClick={() => updateOrderAction(order, 'cancel')}>Annuler</Button>
          )}
          {order.status === 'REFUSEE' && <span>Motif : {order.rejection_reason}</span>}
        </div>
      ),
    },
  ]

  const total = form.lines.reduce((sum, line) => {
    const net = Number(line.quantity || 0) * Number(line.unit_price || 0)
    return sum + net + (net * Number(line.tax_rate || 0) / 100)
  }, 0)

  return (
    <section>
      <PageHeader
        title="Commandes d'achat"
        description="Créez des bons de commande et suivez leur progression."
        actions={<Button onClick={startCreate}>Créer un brouillon</Button>}
      />
      {error && <p className="inline-alert" role="alert">{error}</p>}
      <div className="list-filter">
        <label className="form-field compact-field">
          <span>Statut</span>
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
            <option value="">Tous les statuts</option>
            {statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        loading={isLoading}
        page={page}
        pageSize={25}
        totalItems={count}
        onPageChange={setPage}
        searchValue={search}
        onSearchChange={setSearch}
        searchLabel="Rechercher une commande"
        emptyMessage="Aucune commande trouvée."
      />

      <Modal
        isOpen={isFormOpen}
        onClose={() => setIsFormOpen(false)}
        title={editing ? `Commande ${editing.order_number}` : 'Nouvelle commande'}
        description="Le total est recalculé à partir des lignes, des quantités et des taxes."
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsFormOpen(false)}>Annuler</Button>
            <Button type="submit" form="order-form" loading={isSaving}>
              {editing ? 'Enregistrer' : 'Créer la commande'}
            </Button>
          </>
        )}
      >
        <form id="order-form" onSubmit={saveOrder}>
          <div className="form-grid">
            <SelectField
              label="Fournisseur"
              name="supplier"
              value={form.supplier}
              onChange={changeField}
              required
              options={[
                { value: '', label: suppliers.isLoading ? 'Chargement…' : 'Sélectionner un fournisseur' },
                ...suppliers.rows.map((supplier) => ({
                  value: String(supplier.id),
                  label: supplier.company_name,
                })),
              ]}
            />
            <FormField label="Date de commande" name="order_date" type="date" value={form.order_date} onChange={changeField} />
            <FormField label="Livraison prévue" name="expected_delivery_date" type="date" value={form.expected_delivery_date} onChange={changeField} />
            <TextAreaField label="Conditions" name="terms" value={form.terms} onChange={changeField} />
            <TextAreaField label="Notes" name="notes" value={form.notes} onChange={changeField} />
          </div>
          <div className="line-items-heading">
            <h3>Articles</h3>
            <Button variant="secondary" size="small" onClick={addLine}>Ajouter une ligne</Button>
          </div>
          <div className="line-items">
            {form.lines.map((line, index) => (
              <div className="line-item-row" key={index}>
                <FormField label="Désignation" name="product_name" value={line.product_name} onChange={(event) => changeLine(index, event)} required />
                <FormField label="Quantité" name="quantity" type="number" min="0.001" step="0.001" value={line.quantity} onChange={(event) => changeLine(index, event)} required />
                <FormField label="Prix unitaire HT" name="unit_price" type="number" min="0" step="0.01" value={line.unit_price} onChange={(event) => changeLine(index, event)} required />
                <FormField label="Taxe (%)" name="tax_rate" type="number" min="0" max="100" step="0.01" value={line.tax_rate} onChange={(event) => changeLine(index, event)} />
                <Button variant="ghost" size="small" onClick={() => removeLine(index)} aria-label={`Supprimer la ligne ${index + 1}`}>×</Button>
              </div>
            ))}
          </div>
          <p className="form-total">Total TTC estimé : <strong>{formatAmount(total)}</strong></p>
          {formError && <p className="form-error" role="alert">{formError}</p>}
        </form>
      </Modal>
      <Modal
        isOpen={Boolean(rejecting)}
        onClose={() => { setRejecting(null); setRejectionReason('') }}
        title="Refuser la commande"
        description={rejecting ? `Commande ${rejecting.order_number} — un motif sera conservé dans son historique.` : ''}
        footer={(
          <>
            <Button variant="secondary" onClick={() => { setRejecting(null); setRejectionReason('') }}>Annuler</Button>
            <Button variant="danger" type="submit" form="order-rejection-form" disabled={!rejectionReason.trim()}>Confirmer le refus</Button>
          </>
        )}
      >
        <form id="order-rejection-form" onSubmit={rejectOrder}>
          <TextAreaField
            label="Motif obligatoire"
            name="rejection_reason"
            value={rejectionReason}
            onChange={(event) => setRejectionReason(event.target.value)}
            required
          />
        </form>
      </Modal>
    </section>
  )
}
