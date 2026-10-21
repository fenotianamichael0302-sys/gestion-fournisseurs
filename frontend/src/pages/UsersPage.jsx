import { useState } from 'react'
import { api, getErrorMessage } from '../api/client'
import Button from '../components/Button'
import DataTable from '../components/DataTable'
import { FormField, SelectField } from '../components/FormField'
import Modal from '../components/Modal'
import PageHeader from '../components/PageHeader'
import { useToast } from '../context/useToast'
import useApiList from '../hooks/useApiList'

const roles = [
  { value: 'ADMINISTRATEUR', label: 'Administrateur' },
  { value: 'ACHETEUR', label: 'Acheteur' },
]
const blankUser = () => ({
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  role: 'ACHETEUR',
  is_active: 'true',
  password: '',
})

export default function UsersPage() {
  const toast = useToast()
  const users = useApiList('users')
  const [form, setForm] = useState(blankUser)
  const [editing, setEditing] = useState(null)
  const [isOpen, setIsOpen] = useState(false)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [backupRunning, setBackupRunning] = useState(false)

  function openCreate() {
    setEditing(null)
    setForm(blankUser())
    setFormError('')
    setIsOpen(true)
  }

  function openEdit(user) {
    setEditing(user)
    setForm({
      username: user.username,
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      role: user.role,
      is_active: String(user.is_active),
      password: '',
    })
    setFormError('')
    setIsOpen(true)
  }

  function changeField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function saveUser(event) {
    event.preventDefault()
    setSaving(true)
    setFormError('')
    const payload = {
      username: form.username,
      email: form.email,
      first_name: form.first_name,
      last_name: form.last_name,
      role: form.role,
      is_active: form.is_active === 'true',
      ...(form.password ? { password: form.password } : {}),
    }
    try {
      if (editing) await api.patch(`/users/${editing.id}/`, payload)
      else await api.post('/users/', payload)
      toast.success(editing ? 'Utilisateur modifié.' : 'Utilisateur créé.')
      setIsOpen(false)
      users.refresh()
    } catch (saveError) {
      setFormError(getErrorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  async function createBackup() {
    setBackupRunning(true)
    try {
      const { data } = await api.post('/admin/backup/')
      const size = new Intl.NumberFormat('fr-FR').format(data.size_bytes)
      toast.success(`Sauvegarde créée : ${data.file_name} (${size} octets).`)
    } catch (backupError) {
      toast.error(getErrorMessage(backupError))
    } finally {
      setBackupRunning(false)
    }
  }

  const columns = [
    { key: 'username', header: 'Identifiant', sortable: true },
    { key: 'first_name', header: 'Prénom' },
    { key: 'last_name', header: 'Nom' },
    { key: 'email', header: 'E-mail' },
    { key: 'role', header: 'Rôle', render: (value) => roles.find((role) => role.value === value)?.label || value },
    { key: 'is_active', header: 'État', render: (value) => value ? 'Actif' : 'Désactivé' },
    { key: 'actions', header: 'Actions', render: (_value, user) => <Button variant="ghost" size="small" onClick={() => openEdit(user)}>Modifier</Button> },
  ]

  return (
    <section>
      <PageHeader
        title="Utilisateurs"
        description="Gérez les accès et les rôles de votre espace de travail."
        actions={(
          <div className="admin-actions">
            <Button variant="secondary" loading={backupRunning} onClick={createBackup}>Sauvegarder maintenant</Button>
            <Button onClick={openCreate}>Créer un utilisateur</Button>
          </div>
        )}
      />
      {users.error && <p className="inline-alert" role="alert">{users.error}</p>}
      <DataTable
        columns={columns}
        rows={users.rows}
        loading={users.isLoading}
        page={users.page}
        pageSize={25}
        totalItems={users.count}
        onPageChange={users.setPage}
        searchValue={users.search}
        onSearchChange={users.setSearch}
        searchLabel="Rechercher un utilisateur"
        emptyMessage="Aucun utilisateur trouvé."
      />
      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title={editing ? 'Modifier l’utilisateur' : 'Créer un utilisateur'}
        description="Le mot de passe est facultatif en modification et sera toujours haché côté serveur."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsOpen(false)}>Annuler</Button>
            <Button type="submit" form="user-form" loading={saving}>Enregistrer</Button>
          </>
        )}
      >
        <form id="user-form" className="form-grid" onSubmit={saveUser}>
          <FormField label="Identifiant" name="username" value={form.username} onChange={changeField} required disabled={Boolean(editing)} />
          <FormField label="E-mail" name="email" type="email" value={form.email} onChange={changeField} required />
          <FormField label="Prénom" name="first_name" value={form.first_name} onChange={changeField} required />
          <FormField label="Nom" name="last_name" value={form.last_name} onChange={changeField} required />
          <SelectField label="Rôle" name="role" value={form.role} onChange={changeField} options={roles} />
          <SelectField
            label="Accès"
            name="is_active"
            value={form.is_active}
            onChange={changeField}
            options={[{ value: 'true', label: 'Actif' }, { value: 'false', label: 'Désactivé' }]}
          />
          <FormField label={editing ? 'Nouveau mot de passe (facultatif)' : 'Mot de passe'} name="password" type="password" autoComplete="new-password" value={form.password} onChange={changeField} required={!editing} />
          {formError && <p className="form-error form-field-wide" role="alert">{formError}</p>}
        </form>
      </Modal>
    </section>
  )
}
