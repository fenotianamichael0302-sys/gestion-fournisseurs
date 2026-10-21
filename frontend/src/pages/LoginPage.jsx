import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import { FormField } from '../components/FormField'
import Modal from '../components/Modal'
import { api, getErrorMessage } from '../api/client'
import { useAuth } from '../context/useAuth'
import { useToast } from '../context/useToast'

export default function LoginPage() {
  const { user, login, authError, setAuthError } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isRegistrationOpen, setIsRegistrationOpen] = useState(false)
  const [registration, setRegistration] = useState({ username: '', email: '', first_name: '', last_name: '', password: '', password_confirmation: '' })
  const [registrationError, setRegistrationError] = useState('')
  const [isRegistering, setIsRegistering] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  async function handleSubmit(event) {
    event.preventDefault()
    setIsSubmitting(true)
    setAuthError('')
    try {
      await login(username, password)
      navigate('/dashboard', { replace: true })
    } catch {
      // Le contexte expose déjà le message d'erreur à l'écran.
    } finally {
      setIsSubmitting(false)
    }
  }

  function changeRegistration(event) {
    setRegistration((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function registerBuyer(event) {
    event.preventDefault()
    if (registration.password !== registration.password_confirmation) {
      setRegistrationError('Les deux mots de passe ne correspondent pas.')
      return
    }
    setRegistrationError('')
    setIsRegistering(true)
    try {
      await api.post('/auth/register/', {
        username: registration.username,
        email: registration.email,
        first_name: registration.first_name,
        last_name: registration.last_name,
        password: registration.password,
      })
      setIsRegistrationOpen(false)
      setRegistration({ username: '', email: '', first_name: '', last_name: '', password: '', password_confirmation: '' })
      toast.success('Compte acheteur créé. Vous pouvez maintenant vous connecter.')
    } catch (requestError) {
      setRegistrationError(getErrorMessage(requestError))
    } finally {
      setIsRegistering(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <span className="brand-mark">F</span>
          <span>Gestion Fournisseurs</span>
        </div>
        <p className="eyebrow">Espace de travail</p>
        <h1 id="login-title">Bon retour parmi nous</h1>
        <p className="login-description">Connectez-vous pour gérer vos achats et vos fournisseurs.</p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="username">Identifiant</label>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          {authError && <p className="form-error" role="alert">{authError}</p>}
          <Button className="login-submit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Connexion…' : 'Se connecter'}
          </Button>
        </form>
        <Button variant="secondary" className="register-button" onClick={() => { setRegistrationError(''); setIsRegistrationOpen(true) }}>
          Créer un compte acheteur
        </Button>
        <p className="login-footnote">Accès réservé aux utilisateurs autorisés.</p>
      </section>
      <Modal
        isOpen={isRegistrationOpen}
        onClose={() => setIsRegistrationOpen(false)}
        title="Créer un compte acheteur"
        description="Le nouveau compte disposera automatiquement du rôle Acheteur."
        footer={(
          <>
            <Button variant="secondary" onClick={() => setIsRegistrationOpen(false)}>Annuler</Button>
            <Button type="submit" form="buyer-registration-form" loading={isRegistering}>Créer le compte</Button>
          </>
        )}
      >
        <form id="buyer-registration-form" className="form-grid" onSubmit={registerBuyer}>
          <FormField label="Identifiant" name="username" value={registration.username} onChange={changeRegistration} autoComplete="username" required />
          <FormField label="E-mail" name="email" type="email" value={registration.email} onChange={changeRegistration} autoComplete="email" required />
          <FormField label="Prénom" name="first_name" value={registration.first_name} onChange={changeRegistration} autoComplete="given-name" required />
          <FormField label="Nom" name="last_name" value={registration.last_name} onChange={changeRegistration} autoComplete="family-name" required />
          <FormField label="Mot de passe" name="password" type="password" value={registration.password} onChange={changeRegistration} autoComplete="new-password" required />
          <FormField label="Confirmer le mot de passe" name="password_confirmation" type="password" value={registration.password_confirmation} onChange={changeRegistration} autoComplete="new-password" required />
          {registrationError && <p className="form-error form-field-wide" role="alert">{registrationError}</p>}
        </form>
      </Modal>
    </main>
  )
}
