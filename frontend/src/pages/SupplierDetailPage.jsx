import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, getErrorMessage } from '../api/client'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { useAuth } from '../context/useAuth'
import useApiList from '../hooks/useApiList'

const tabs = ['Commandes', 'Factures', 'Paiements']
const orderStatus = { EN_ATTENTE: 'En attente', VALIDEE: 'Validée', LIVREE: 'Livrée', ANNULEE: 'Annulée' }
const invoiceStatus = { NON_PAYEE: 'Non payée', PARTIELLEMENT_PAYEE: 'Partiellement payée', PAYEE: 'Payée', EN_RETARD: 'En retard' }
const paymentMethod = { VIREMENT: 'Virement', CHEQUE: 'Chèque', ESPECES: 'Espèces', MOBILE_MONEY: 'Mobile money', CARTE: 'Carte' }

function money(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

function Detail({ label, value }) {
  return <div className="detail-item"><dt>{label}</dt><dd>{value || '—'}</dd></div>
}

export default function SupplierDetailPage() {
  const { user } = useAuth()
  const { supplierId } = useParams()
  const [supplier, setSupplier] = useState(null)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState(tabs[0])
  const query = useMemo(() => ({ supplier: supplierId }), [supplierId])
  const orders = useApiList('orders', query)
  const invoices = useApiList('invoices', query)
  const payments = useApiList('payments', query)

  useEffect(() => {
    let active = true
    api.get(`/suppliers/${supplierId}/`)
      .then(({ data }) => { if (active) setSupplier(data) })
      .catch((requestError) => { if (active) setError(getErrorMessage(requestError)) })
    return () => { active = false }
  }, [supplierId])

  const columns = activeTab === 'Commandes'
    ? [
        { key: 'order_number', header: 'N° commande' },
        { key: 'order_date', header: 'Date' },
        { key: 'total_ttc', header: 'Total TTC', render: (value) => money(value) },
        { key: 'status', header: 'Statut', render: (value) => orderStatus[value] || value },
      ]
    : activeTab === 'Factures'
      ? [
          { key: 'invoice_number', header: 'N° facture' },
          { key: 'invoice_date', header: 'Date' },
          { key: 'due_date', header: 'Échéance' },
          { key: 'total_ttc', header: 'Total TTC', render: (value) => money(value) },
          { key: 'balance_due', header: 'Reste dû', render: (value) => money(value) },
          { key: 'status', header: 'Statut', render: (value) => invoiceStatus[value] || value },
        ]
      : [
          { key: 'payment_date', header: 'Date' },
          { key: 'invoice_number', header: 'Facture' },
          { key: 'amount', header: 'Montant', render: (value) => money(value) },
          { key: 'method', header: 'Mode', render: (value) => paymentMethod[value] || value },
          { key: 'reference', header: 'Référence' },
        ]
  const history = activeTab === 'Commandes' ? orders : activeTab === 'Factures' ? invoices : payments

  if (error) return <p className="inline-alert" role="alert">{error}</p>
  if (!supplier) return <p className="placeholder-card" role="status">Chargement du fournisseur…</p>

  return (
    <section>
      <PageHeader
        eyebrow="Fiche fournisseur"
        title={supplier.company_name}
        description={supplier.contact_name ? `Contact principal : ${supplier.contact_name}` : 'Coordonnées et historique des achats'}
        actions={<Link className="button button-secondary" to="/suppliers">Retour aux fournisseurs</Link>}
      />
      <div className="supplier-detail-grid">
        <article className="panel-card">
          <h2>Coordonnées</h2>
          <dl className="detail-grid">
            <Detail label="E-mail" value={supplier.email} />
            <Detail label="Téléphone" value={supplier.phone} />
            <Detail label="Adresse" value={[supplier.street, supplier.city, supplier.postal_code, supplier.country].filter(Boolean).join(', ')} />
            <Detail label="NIF / STAT" value={supplier.tax_id} />
            <Detail label="Statut" value={supplier.status} />
            <Detail label="Évaluations" value={supplier.evaluation_count || 0} />
            <Detail label="Qualité moyenne" value={supplier.quality_rating == null ? '—' : `${supplier.quality_rating.toFixed(1)} / 5`} />
            <Detail label="Respect des délais moyen" value={supplier.delivery_rating == null ? '—' : `${supplier.delivery_rating.toFixed(1)} / 5`} />
            <Detail label="Prix moyen" value={supplier.price_rating == null ? '—' : `${supplier.price_rating.toFixed(1)} / 5`} />
            <Detail label="Fiabilité moyenne" value={supplier.reliability_rating == null ? '—' : `${supplier.reliability_rating.toFixed(1)} / 5`} />
            <Detail label="Notes" value={supplier.notes} />
          </dl>
        </article>
        {user.role === 'ADMINISTRATEUR' && (
          <article className="panel-card">
            <h2>Informations bancaires</h2>
            <dl className="detail-grid">
              <Detail label="Banque" value={supplier.bank_name} />
              <Detail label="IBAN / RIB" value={supplier.bank_account} />
              <Detail label="SWIFT" value={supplier.swift} />
            </dl>
          </article>
        )}
      </div>
      <article className="panel-card supplier-history">
        <div className="panel-heading"><h2>Historique des achats</h2></div>
        <div className="tab-list" role="tablist" aria-label="Historique fournisseur">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab ? 'tab-button active' : 'tab-button'}
              key={tab}
              type="button"
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        {history.error && <p className="inline-alert" role="alert">{history.error}</p>}
        <DataTable
          columns={columns}
          rows={history.rows}
          loading={history.isLoading}
          page={history.page}
          pageSize={25}
          totalItems={history.count}
          onPageChange={history.setPage}
          emptyMessage={`Aucun élément ${activeTab.toLowerCase()} pour ce fournisseur.`}
        />
      </article>
    </section>
  )
}
