import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const blankEvaluation = () => ({
  supplier: '',
  order: '',
  quality_rating: '5',
  delivery_rating: '5',
  price_rating: '5',
  reliability_rating: '5',
  comment: '',
})

function rating(value) {
  return `${Number(value).toFixed(1)} / 5`
}

export default function EvaluationsPage() {
  const toast = useToast()
  const evaluations = useApiList('supplier-evaluations')
  const suppliers = useApiList('suppliers')
  const orders = useApiList('orders', { status: 'LIVREE' })
  const [form, setForm] = useState(blankEvaluation)
  const [isOpen, setIsOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  function updateField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
      ...(event.target.name === 'supplier' ? { order: '' } : {}),
    }))
  }

  async function saveEvaluation(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await api.post('/supplier-evaluations/', {
        ...form,
        supplier: Number(form.supplier),
        order: Number(form.order),
        quality_rating: Number(form.quality_rating),
        delivery_rating: Number(form.delivery_rating),
        price_rating: Number(form.price_rating),
        reliability_rating: Number(form.reliability_rating),
      })
      toast.success('Évaluation fournisseur enregistrée.')
      setIsOpen(false)
      evaluations.refresh()
      suppliers.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const selectedOrders = orders.rows.filter(
    (order) => String(order.supplier) === form.supplier,
  )
  const columns = [
    { key: 'created_at', header: 'Date', render: (value) => new Date(value).toLocaleDateString('fr-FR') },
    { key: 'supplier_name', header: 'Fournisseur' },
    { key: 'order_number', header: 'Commande' },
    { key: 'quality_rating', header: 'Qualité', render: rating },
    { key: 'delivery_rating', header: 'Délais', render: rating },
    { key: 'price_rating', header: 'Prix', render: rating },
    { key: 'reliability_rating', header: 'Fiabilité', render: rating },
    { key: 'comment', header: 'Commentaire' },
    { key: 'evaluated_by_username', header: 'Évalué par' },
  ]

  return (
    <section>
      <PageHeader
        title="Évaluations fournisseurs"
        description="Évaluez les fournisseurs à partir des commandes entièrement livrées et consultez l’historique réel."
        actions={<Button onClick={() => { setForm(blankEvaluation()); setFormError(''); setIsOpen(true) }}>Évaluer un fournisseur</Button>}
      />
      {evaluations.error && <p className="inline-alert" role="alert">{evaluations.error}</p>}
      <DataTable
        columns={columns}
        rows={evaluations.rows}
        loading={evaluations.isLoading}
        page={evaluations.page}
        pageSize={25}
        totalItems={evaluations.count}
        onPageChange={evaluations.setPage}
        emptyMessage="Aucune évaluation enregistrée."
      />
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Nouvelle évaluation"
        description="Une seule évaluation par utilisateur et par commande entièrement livrée."
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsOpen(false)}>Annuler</Button>
            <Button type="submit" form="evaluation-form" loading={saving}>Enregistrer l’évaluation</Button>
          </>
        )}
      >
        <form id="evaluation-form" className="form-grid" onSubmit={saveEvaluation}>
          <SelectField
            label="Fournisseur"
            name="supplier"
            value={form.supplier}
            onChange={updateField}
            required
            options={[
              { value: '', label: 'Sélectionner un fournisseur' },
              ...suppliers.rows.map((supplier) => ({
                value: String(supplier.id),
                label: supplier.company_name,
              })),
            ]}
          />
          <SelectField
            label="Commande livrée"
            name="order"
            value={form.order}
            onChange={updateField}
            required
            disabled={!form.supplier}
            options={[
              { value: '', label: orders.isLoading ? 'Chargement…' : 'Sélectionner une commande' },
              ...selectedOrders.map((order) => ({
                value: String(order.id),
                label: order.order_number,
              })),
            ]}
          />
          {[
            ['quality_rating', 'Qualité des produits'],
            ['delivery_rating', 'Respect des délais'],
            ['price_rating', 'Compétitivité des prix'],
            ['reliability_rating', 'Fiabilité'],
          ].map(([name, label]) => (
            <SelectField
              key={name}
              label={label}
              name={name}
              value={form[name]}
              onChange={updateField}
              options={[1, 2, 3, 4, 5].map((score) => ({
                value: String(score),
                label: `${score} / 5`,
              }))}
            />
          ))}
          <TextAreaField label="Commentaire" name="comment" value={form.comment} onChange={updateField} />
          {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
