import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const quoteStatuses = {
  DEMANDE: 'Demandé',
  RECU: 'Reçu',
  REFUSE: 'Refusé',
}

const emptyRequest = () => ({ product_name: '', quantity: '1', supplier_ids: [] })
const emptyResponse = () => ({
  unit_price: '',
  tax_rate: '0',
  delivery_days: '',
  quality_rating: '',
  payment_terms: '',
  notes: '',
})

function amount(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

export default function QuotesPage() {
  const toast = useToast()
  const quotes = useApiList('quotes')
  const suppliers = useApiList('suppliers')
  const [request, setRequest] = useState(emptyRequest)
  const [response, setResponse] = useState(emptyResponse)
  const [isRequestOpen, setIsRequestOpen] = useState(false)
  const [receiving, setReceiving] = useState(null)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  function updateRequest(event) {
    const { name, value } = event.target
    setRequest((current) => ({
      ...current,
      [name]: name === 'supplier_ids'
        ? Array.from(event.target.selectedOptions, (option) => option.value)
        : value,
    }))
  }

  function updateResponse(event) {
    setResponse((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function createRequests(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/quotes/request/', {
        product_name: request.product_name,
        quantity: request.quantity,
        supplier_ids: request.supplier_ids.map(Number),
      })
      toast.success('Demandes enregistrées. Aucun courriel n’a été envoyé.')
      setIsRequestOpen(false)
      setRequest(emptyRequest())
      quotes.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function saveResponse(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post(`/quotes/${receiving.id}/receive/`, {
        ...response,
        unit_price: response.unit_price,
        tax_rate: response.tax_rate,
        delivery_days: response.delivery_days === '' ? null : Number(response.delivery_days),
        quality_rating: response.quality_rating === '' ? null : Number(response.quality_rating),
      })
      toast.success('Offre reçue enregistrée.')
      setReceiving(null)
      quotes.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function declineQuote(quote) {
    const notes = window.prompt(`Motif du refus du devis de ${quote.supplier_name} :`)
    if (notes === null) return
    try {
      await api.post(`/quotes/${quote.id}/decline/`, { notes })
      toast.success('Refus du devis enregistré.')
      quotes.refresh()
    } catch (declineError) {
      toast.error(getErrorMessage(declineError))
    }
  }

  const columns = [
    {
      key: 'comparison_id',
      header: 'Comparaison',
      render: (value) => value.slice(0, 8).toUpperCase(),
    },
    { key: 'product_name', header: 'Produit / service', sortable: true },
    { key: 'quantity', header: 'Quantité' },
    { key: 'supplier_name', header: 'Fournisseur', sortable: true },
    {
      key: 'unit_price',
      header: 'Prix unitaire HT',
      sortable: true,
      render: (value) => value == null ? '—' : amount(value),
    },
    { key: 'delivery_days', header: 'Délai (jours)', sortable: true, render: (value) => value ?? '—' },
    { key: 'quality_rating', header: 'Qualité', render: (value) => value == null ? '—' : `${value} / 5` },
    { key: 'payment_terms', header: 'Conditions de paiement' },
    { key: 'status', header: 'Statut', render: (value) => quoteStatuses[value] || value },
    {
      key: 'actions',
      header: 'Actions',
      render: (_value, quote) => quote.status === 'DEMANDE' && (
        <div className="table-actions">
          <Button
            size="small"
            onClick={() => { setReceiving(quote); setResponse(emptyResponse()); setFormError('') }}
          >
            Enregistrer la réponse
          </Button>
          <Button variant="ghost" size="small" onClick={() => declineQuote(quote)}>Refusé</Button>
        </div>
      ),
    },
  ]

  return (
    <section>
      <PageHeader
        title="Demandes et comparaison des devis"
        description="Enregistrez les demandes faites à plusieurs fournisseurs et comparez les réponses saisies."
        actions={<Button onClick={() => { setRequest(emptyRequest()); setFormError(''); setIsRequestOpen(true) }}>Nouvelle comparaison</Button>}
      />
      <p className="inline-alert" role="note">
        Les demandes sont enregistrées dans l’application uniquement ; aucun courriel ni autre envoi externe n’est effectué.
      </p>
      {quotes.error && <p className="inline-alert" role="alert">{quotes.error}</p>}
      <DataTable
        columns={columns}
        rows={quotes.rows}
        loading={quotes.isLoading}
        page={quotes.page}
        pageSize={25}
        totalItems={quotes.count}
        onPageChange={quotes.setPage}
        searchValue={quotes.search}
        onSearchChange={quotes.setSearch}
        searchLabel="Rechercher un devis ou fournisseur"
        emptyMessage="Aucune demande de devis enregistrée."
      />
      <Modal
        isOpen={isRequestOpen}
        onClose={() => setIsRequestOpen(false)}
        title="Demander plusieurs devis"
        description="Choisissez les fournisseurs à comparer. L’application conserve la demande mais ne la transmet pas."
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsRequestOpen(false)}>Annuler</Button>
            <Button type="submit" form="quote-request-form" loading={saving}>Enregistrer les demandes</Button>
          </>
        )}
      >
        <form id="quote-request-form" className="form-grid" onSubmit={createRequests}>
          <FormField label="Produit ou service" name="product_name" value={request.product_name} onChange={updateRequest} required />
          <FormField label="Quantité souhaitée" name="quantity" type="number" min="0.001" step="0.001" value={request.quantity} onChange={updateRequest} required />
          <label className="form-field form-field-wide">
            <span>Fournisseurs à comparer</span>
            <select
              name="supplier_ids"
              multiple
              required
              value={request.supplier_ids}
              onChange={updateRequest}
              size={Math.min(Math.max(suppliers.rows.length, 3), 8)}
            >
              {suppliers.rows
                .filter((supplier) => supplier.status === 'ACTIF')
                .map((supplier) => (
                  <option key={supplier.id} value={String(supplier.id)}>{supplier.company_name}</option>
                ))}
            </select>
            <small>Maintenez Ctrl (Windows) ou Cmd (macOS) pour sélectionner plusieurs fournisseurs.</small>
          </label>
          {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
        </form>
      </Modal>
      <Modal
        isOpen={Boolean(receiving)}
        onClose={() => setReceiving(null)}
        title={receiving ? `Réponse reçue — ${receiving.supplier_name}` : 'Réponse reçue'}
        description={receiving ? `${receiving.product_name} · ${receiving.quantity} demandé(s)` : ''}
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setReceiving(null)}>Annuler</Button>
            <Button type="submit" form="quote-response-form" loading={saving}>Enregistrer l’offre</Button>
          </>
        )}
      >
        <form id="quote-response-form" className="form-grid" onSubmit={saveResponse}>
          <FormField label="Prix unitaire HT" name="unit_price" type="number" min="0" step="0.01" value={response.unit_price} onChange={updateResponse} required />
          <FormField label="Taxe (%)" name="tax_rate" type="number" min="0" max="100" step="0.01" value={response.tax_rate} onChange={updateResponse} />
          <FormField label="Délai de livraison (jours)" name="delivery_days" type="number" min="0" step="1" value={response.delivery_days} onChange={updateResponse} />
          <SelectField
            label="Qualité annoncée / évaluée"
            name="quality_rating"
            value={response.quality_rating}
            onChange={updateResponse}
            options={[
              { value: '', label: 'Non renseignée' },
              ...[1, 2, 3, 4, 5].map((score) => ({ value: String(score), label: `${score} / 5` })),
            ]}
          />
          <FormField label="Conditions de paiement" name="payment_terms" value={response.payment_terms} onChange={updateResponse} />
          <TextAreaField label="Notes" name="notes" value={response.notes} onChange={updateResponse} />
          {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
