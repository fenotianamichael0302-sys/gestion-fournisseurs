import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField, TextAreaField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import useApiList from '../hooks/useApiList'
import { useToast } from '../context/useToast'
import { useAuth } from '../context/useAuth'

const emptySupplier = {
  company_name: '',
  contact_name: '',
  email: '',
  phone: '',
  street: '',
  city: '',
  postal_code: '',
  country: '',
  tax_id: '',
  bank_name: '',
  bank_account: '',
  swift: '',
  status: 'ACTIF',
  notes: '',
}

const statusLabels = { ACTIF: 'Actif', INACTIF: 'Inactif', BLOQUE: 'Bloqué' }

export default function SuppliersPage() {
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user.role === 'ADMINISTRATEUR'
  const [status, setStatus] = useState('')
  const query = useMemo(() => status ? { status } : {}, [status])
  const { rows, page, setPage, search, setSearch, count, isLoading, error, refresh } =
    useApiList('suppliers', query)
  const [form, setForm] = useState(emptySupplier)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [formError, setFormError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  function startCreate() {
    setForm({ ...emptySupplier })
    setEditing(null)
    setFormError('')
    setIsFormOpen(true)
  }

  function startEdit(supplier) {
    setForm(Object.fromEntries(Object.keys(emptySupplier).map((key) => [key, supplier[key] ?? ''])))
    setEditing(supplier)
    setFormError('')
    setIsFormOpen(true)
  }

  function updateForm(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function saveSupplier(event) {
    event.preventDefault()
    setFormError('')
    setIsSaving(true)
    try {
      if (editing) await api.patch(`/suppliers/${editing.id}/`, form)
      else await api.post('/suppliers/', form)
      toast.success(editing ? 'Fournisseur modifié.' : 'Fournisseur ajouté.')
      setIsFormOpen(false)
      setEditing(null)
      refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setIsSaving(false)
    }
  }

  async function deleteSupplier() {
    try {
      await api.delete(`/suppliers/${deleting.id}/`)
      toast.success('Fournisseur archivé.')
      setDeleting(null)
      refresh()
    } catch (deleteError) {
      toast.error(getErrorMessage(deleteError))
    }
  }

  const columns = [
    {
      key: 'company_name',
      header: 'Raison sociale',
      sortable: true,
      render: (value, row) => <Link className="table-primary-link" to={`/suppliers/${row.id}`}>{value}</Link>,
    },
    { key: 'contact_name', header: 'Contact', sortable: true },
    { key: 'email', header: 'E-mail' },
    { key: 'phone', header: 'Téléphone' },
    {
      key: 'status',
      header: 'Statut',
      render: (value) => <span className={`status-badge status-${value.toLowerCase()}`}>{statusLabels[value]}</span>,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (_value, row) => (
        <div className="table-actions">
          {isAdmin && (
            <>
              <Button variant="ghost" size="small" onClick={() => startEdit(row)}>Modifier</Button>
              <Button variant="danger" size="small" onClick={() => setDeleting(row)}>Archiver</Button>
            </>
          )}
        </div>
      ),
    },
  ]

  return (
    <section>
      <PageHeader
        title="Fournisseurs"
        description="Centralisez vos contacts, coordonnées et informations administratives."
        actions={isAdmin && <Button onClick={startCreate}>Ajouter un fournisseur</Button>}
      />
      {error && <p className="inline-alert" role="alert">{error}</p>}
      <div className="list-filter">
        <label className="form-field compact-field">
          <span>Statut</span>
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}>
            <option value="">Tous les statuts</option>
            <option value="ACTIF">Actif</option>
            <option value="INACTIF">Inactif</option>
            <option value="BLOQUE">Bloqué</option>
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
        searchLabel="Rechercher un fournisseur"
        emptyMessage="Aucun fournisseur trouvé."
      />

      <Modal
        isOpen={isFormOpen}
        onClose={() => { setIsFormOpen(false); setEditing(null) }}
        title={editing ? 'Modifier le fournisseur' : 'Ajouter un fournisseur'}
        description="Les informations pourront être mises à jour ultérieurement."
        size="large"
        footer={(
          <>
            <Button variant="secondary" onClick={() => { setIsFormOpen(false); setEditing(null) }}>Annuler</Button>
            <Button type="submit" form="supplier-form" loading={isSaving}>
              {editing ? 'Enregistrer' : 'Créer le fournisseur'}
            </Button>
          </>
        )}
      >
        {form && (
          <form id="supplier-form" className="form-grid" onSubmit={saveSupplier}>
            <FormField label="Raison sociale" name="company_name" value={form.company_name} onChange={updateForm} required />
            <FormField label="Personne de contact" name="contact_name" value={form.contact_name} onChange={updateForm} />
            <FormField label="E-mail" name="email" type="email" value={form.email} onChange={updateForm} />
            <FormField label="Téléphone" name="phone" type="tel" value={form.phone} onChange={updateForm} />
            <FormField label="Rue et adresse" name="street" value={form.street} onChange={updateForm} />
            <FormField label="Ville" name="city" value={form.city} onChange={updateForm} />
            <FormField label="Code postal" name="postal_code" value={form.postal_code} onChange={updateForm} />
            <FormField label="Pays" name="country" value={form.country} onChange={updateForm} />
            <FormField label="NIF / STAT" name="tax_id" value={form.tax_id} onChange={updateForm} />
            <FormField label="Banque" name="bank_name" value={form.bank_name} onChange={updateForm} />
            <FormField label="IBAN / RIB" name="bank_account" value={form.bank_account} onChange={updateForm} />
            <FormField label="SWIFT" name="swift" value={form.swift} onChange={updateForm} />
            <SelectField
              label="Statut"
              name="status"
              value={form.status}
              onChange={updateForm}
              options={[
                { value: 'ACTIF', label: 'Actif' },
                { value: 'INACTIF', label: 'Inactif' },
                { value: 'BLOQUE', label: 'Bloqué' },
              ]}
            />
            <TextAreaField label="Notes" name="notes" value={form.notes} onChange={updateForm} />
            {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
          </form>
        )}
      </Modal>
      <Modal
        isOpen={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        title="Archiver le fournisseur ?"
        description="Le fournisseur sera masqué des listes, mais ses commandes et factures resteront conservées."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setDeleting(null)}>Annuler</Button>
            <Button variant="danger" onClick={deleteSupplier}>Archiver</Button>
          </>
        )}
      >
        <p>{deleting?.company_name}</p>
      </Modal>
    </section>
  )
}
