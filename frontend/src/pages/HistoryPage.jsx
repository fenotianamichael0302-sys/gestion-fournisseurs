import { useMemo, useState } from 'react'
import DataTable from '../components/DataTable'
import { FormField, SelectField } from '../components/FormField'
import PageHeader from '../components/PageHeader'
import useApiList from '../hooks/useApiList'

const auditActions = [
  { value: 'CREATE', label: 'Création' },
  { value: 'UPDATE', label: 'Modification' },
  { value: 'DELETE', label: 'Suppression' },
  { value: 'STATUS_CHANGE', label: 'Changement de statut' },
  { value: 'LOGIN', label: 'Connexion' },
  { value: 'LOGOUT', label: 'Déconnexion' },
]

export default function HistoryPage() {
  const [filters, setFilters] = useState({ user: '', action: '', date_from: '', date_to: '' })
  const query = useMemo(
    () => Object.fromEntries(Object.entries(filters).filter(([, value]) => value)),
    [filters],
  )
  const history = useApiList('audit', query)
  const users = useApiList('users')

  function changeFilter(event) {
    setFilters((current) => ({ ...current, [event.target.name]: event.target.value }))
    history.setPage(1)
  }

  const columns = [
    { key: 'created_at', header: 'Date et heure', sortable: true, render: (value) => new Date(value).toLocaleString('fr-FR') },
    { key: 'actor_username', header: 'Utilisateur', sortable: true },
    { key: 'action_label', header: 'Action' },
    { key: 'content_type_name', header: 'Type d’objet' },
    { key: 'object_repr', header: 'Objet' },
    { key: 'ip_address', header: 'Adresse IP' },
    {
      key: 'changes',
      header: 'Détails',
      render: (_value, event) => (
        <details className="audit-details">
          <summary>Voir les valeurs</summary>
          <pre>{JSON.stringify({ avant: event.old_values, après: event.new_values }, null, 2)}</pre>
        </details>
      ),
    },
  ]

  return (
    <section>
      <PageHeader title="Historique des actions" description="Consultez les opérations enregistrées et les valeurs modifiées." />
      {history.error && <p className="inline-alert" role="alert">{history.error}</p>}
      <div className="list-filter audit-filters">
        <SelectField
          label="Utilisateur"
          name="user"
          value={filters.user}
          onChange={changeFilter}
          options={[
            { value: '', label: 'Tous les utilisateurs' },
            ...users.rows.map((user) => ({ value: String(user.id), label: user.username })),
          ]}
        />
        <SelectField label="Action" name="action" value={filters.action} onChange={changeFilter} options={[{ value: '', label: 'Toutes les actions' }, ...auditActions]} />
        <FormField label="Depuis" name="date_from" type="date" value={filters.date_from} onChange={changeFilter} />
        <FormField label="Jusqu’au" name="date_to" type="date" value={filters.date_to} onChange={changeFilter} />
      </div>
      <DataTable
        columns={columns}
        rows={history.rows}
        loading={history.isLoading}
        page={history.page}
        pageSize={25}
        totalItems={history.count}
        onPageChange={history.setPage}
        emptyMessage="Aucune action ne correspond aux filtres."
      />
    </section>
  )
}
