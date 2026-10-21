import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, getErrorMessage } from '../api/client'
import DataTable from '../components/DataTable'
import PageHeader from '../components/PageHeader'
import { useAuth } from '../context/useAuth'

const statusColors = ['#f79009', '#2457d6', '#12b76a', '#f04438', '#7a5af8', '#06aed4', '#2e90fa', '#667085']

function money(value) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    .format(Number(value || 0))
}

function ariary(value) {
  return `${money(value)} Ar`
}

function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('fr-FR').format(new Date(`${value}T00:00:00`))
}

function DashboardFrame({ user, error, children }) {
  return (
    <section>
      <PageHeader
        eyebrow="Vue d’ensemble"
        title={`Bonjour${user.first_name ? ` ${user.first_name}` : ''}`}
        description="Voici la situation actuelle de vos achats et de vos engagements."
      />
      {error && <p className="inline-alert" role="alert">{error}</p>}
      {children}
    </section>
  )
}

function AdminDashboard({ data }) {
  const kpis = [
    ['Fournisseurs', data.total_suppliers, 'Référencés'],
    ['Fournisseurs actifs', data.active_suppliers, 'Autorisés pour les commandes'],
    ['Fournisseurs inactifs', data.inactive_suppliers, 'Archivés exclus'],
    ['Commandes en cours', data.orders_in_progress, 'En attente ou validées'],
    ['Factures impayées', data.unpaid_invoices, 'Avec un solde restant'],
    ['Achats totaux', money(data.total_purchases), 'Commandes validées et livraisons'],
  ]

  return (
    <>
      <div className="kpi-grid">
        {kpis.map(([label, value, caption]) => (
          <article className="kpi-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{caption}</small>
          </article>
        ))}
      </div>
      <div className="dashboard-chart-grid">
        <article className="panel-card">
          <div className="panel-heading">
            <h2>Achats par mois</h2>
            <span>12 derniers mois</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.purchases_by_month}>
                <CartesianGrid stroke="#edf0f5" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={(value) => new Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(value)} />
                <Tooltip formatter={(value) => money(value)} />
                <Bar dataKey="total" fill="#2457d6" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
        <article className="panel-card">
          <div className="panel-heading">
            <h2>Statut des commandes</h2>
            <span>Répartition actuelle</span>
          </div>
          <div className="chart-area chart-area-small">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.orders_by_status} dataKey="total" nameKey="label" innerRadius={55} outerRadius={90} paddingAngle={3}>
                  {data.orders_by_status.map((entry, index) => <Cell key={entry.status} fill={statusColors[index % statusColors.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="chart-legend">
            {data.orders_by_status.map((item, index) => (
              <li key={item.status}><span style={{ backgroundColor: statusColors[index % statusColors.length] }} />{item.label}<strong>{item.total}</strong></li>
            ))}
          </ul>
        </article>
      </div>
      <div className="dashboard-lower-grid">
        <article className="panel-card">
          <div className="panel-heading"><h2>Principaux fournisseurs</h2><Link to="/reports">Tous les rapports</Link></div>
          {data.top_suppliers.length ? (
            <ol className="ranked-list">
              {data.top_suppliers.map((item, index) => (
                <li key={item.supplier}><span className="rank-number">{index + 1}</span><span>{item.supplier}</span><strong>{money(item.total)}</strong></li>
              ))}
            </ol>
          ) : <p className="empty-state">Les dépenses apparaîtront après la création de commandes.</p>}
        </article>
        <article className="panel-card">
          <div className="panel-heading"><h2>Alertes</h2><Link to="/invoices">Voir les factures</Link></div>
          <div className="alert-list">
            {data.alerts.overdue_invoices.map((invoice) => (
              <div className="dashboard-alert alert-danger" key={`late-${invoice.id}`}>
                <span>Facture en retard</span>
                <strong>{invoice.invoice_number} · {invoice.supplier_name || invoice.supplier}</strong>
                <small>Échéance {invoice.due_date} · {money(invoice.balance_due)} dus</small>
              </div>
            ))}
            {data.alerts.due_soon_invoices.map((invoice) => (
              <div className="dashboard-alert alert-warning" key={`due-${invoice.id}`}>
                <span>Échéance proche</span>
                <strong>{invoice.invoice_number} · {invoice.supplier_name || invoice.supplier}</strong>
                <small>Échéance {invoice.due_date} · {money(invoice.balance_due)} dus</small>
              </div>
            ))}
            {data.alerts.old_pending_orders.map((order) => (
              <div className="dashboard-alert alert-warning" key={`order-${order.id}`}>
                <span>Commande en attente depuis plus de 30 jours</span>
                <strong>{order.order_number} · {order.supplier_name || order.supplier}</strong>
                <small>Créée le {order.order_date}</small>
              </div>
            ))}
            {data.alerts.overdue_deliveries.map((order) => (
              <div className="dashboard-alert alert-danger" key={`delivery-${order.id}`}>
                <span>Livraison en retard</span>
                <strong>{order.order_number} · {order.supplier_name || order.supplier}</strong>
                <small>Prévue le {order.expected_delivery_date}</small>
              </div>
            ))}
            {!data.alerts.overdue_invoices.length
              && !data.alerts.due_soon_invoices.length
              && !data.alerts.old_pending_orders.length
              && !data.alerts.overdue_deliveries.length
              && <p className="empty-state">Aucune alerte à traiter.</p>}
          </div>
        </article>
      </div>
    </>
  )
}

function BuyerDashboard({ data }) {
  const kpis = [
    ['Mes commandes', data.total_orders, 'Commandes créées par mon compte'],
    ['Commandes en attente', data.pending_orders, 'Soumises à validation'],
    ['Commandes validées', data.approved_orders, 'Approuvées par un administrateur'],
    ['Livraisons à réceptionner', data.deliveries_to_receive, 'À recevoir ou à terminer'],
    ['Factures à payer', data.unpaid_invoices, 'Factures liées à mes opérations'],
    ['Montant de mes achats', ariary(data.total_purchases), 'Commandes validées, hors brouillons et refus'],
  ]
  const columns = [
    { key: 'order_number', header: 'N° commande' },
    { key: 'supplier_name', header: 'Fournisseur' },
    { key: 'order_date', header: 'Date', render: formatDate },
    { key: 'total_ttc', header: 'Montant TTC', render: ariary },
    {
      key: 'status_label',
      header: 'Statut',
      render: (label, order) => <span className={`status-badge status-${order.status.toLowerCase()}`}>{label}</span>,
    },
    { key: 'expected_delivery_date', header: 'Livraison prévue', render: formatDate },
    {
      key: 'details',
      header: 'Détails',
      render: (_value, order) => (
        <details className="buyer-order-detail">
          <summary>Voir les détails</summary>
          <div className="buyer-order-detail-content">
            <strong>{order.order_number} · {order.supplier_name}</strong>
            <span>Commande du {formatDate(order.order_date)}</span>
            <span>Statut : {order.status_label}</span>
            <span>Livraison prévue : {formatDate(order.expected_delivery_date)}</span>
            <ul>
              {order.lines.map((line, index) => (
                <li key={`${order.id}-${index}`}>
                  {line.product_name} · {line.quantity} × {ariary(line.unit_price)}
                </li>
              ))}
            </ul>
            <Link to="/orders">Ouvrir mes commandes</Link>
          </div>
        </details>
      ),
    },
  ]

  return (
    <>
      <div className="kpi-grid">
        {kpis.map(([label, value, caption]) => (
          <article className="kpi-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{caption}</small>
          </article>
        ))}
      </div>
      <div className="dashboard-chart-grid">
        <article className="panel-card">
          <div className="panel-heading">
            <h2>Évolution de mes achats</h2>
            <span>12 derniers mois</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.purchases_by_month}>
                <CartesianGrid stroke="#edf0f5" vertical={false} />
                <XAxis dataKey="month" tickLine={false} axisLine={false} />
                <YAxis tickLine={false} axisLine={false} tickFormatter={(value) => new Intl.NumberFormat('fr-FR', { notation: 'compact' }).format(value)} />
                <Tooltip formatter={(value) => ariary(value)} />
                <Bar dataKey="total" fill="#2457d6" radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
        <article className="panel-card">
          <div className="panel-heading">
            <h2>Mes commandes par statut</h2>
            <span>Répartition de mes commandes</span>
          </div>
          <div className="chart-area chart-area-small">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={data.orders_by_status} dataKey="total" nameKey="label" innerRadius={55} outerRadius={90} paddingAngle={3}>
                  {data.orders_by_status.map((entry, index) => <Cell key={entry.status} fill={statusColors[index % statusColors.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="chart-legend">
            {data.orders_by_status.map((item, index) => (
              <li key={item.status}><span style={{ backgroundColor: statusColors[index % statusColors.length] }} />{item.label}<strong>{item.total}</strong></li>
            ))}
          </ul>
        </article>
      </div>
      <article className="panel-card buyer-recent-orders">
        <div className="panel-heading">
          <h2>Mes dernières commandes</h2>
          <Link to="/orders">Toutes mes commandes</Link>
        </div>
        <DataTable
          columns={columns}
          rows={data.recent_orders}
          pageSize={8}
          emptyMessage="Vous n’avez pas encore créé de commande."
        />
      </article>
    </>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    api.get('/reports/dashboard/')
      .then(({ data: result }) => { if (active) setData(result) })
      .catch((requestError) => { if (active) setError(getErrorMessage(requestError)) })
    return () => { active = false }
  }, [])

  return (
    <DashboardFrame user={user} error={error}>
      {!data && !error && <p className="placeholder-card" role="status">Chargement des indicateurs…</p>}
      {data && (user.role === 'ADMINISTRATEUR'
        ? <AdminDashboard data={data} />
        : <BuyerDashboard data={data} />)}
    </DashboardFrame>
  )
}
