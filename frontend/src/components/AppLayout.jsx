import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/useAuth'
import Button from './Button'

const commonLinks = [
  ['dashboard', 'Tableau de bord'],
  ['suppliers', 'Fournisseurs'],
  ['quotes', 'Devis'],
  ['orders', 'Commandes'],
  ['deliveries', 'Livraisons'],
  ['evaluations', 'Évaluations'],
  ['invoices', 'Factures'],
  ['payments', 'Paiements'],
  ['reports', 'Rapports'],
]

export default function AppLayout() {
  const { user, logout, authError } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user.role === 'ADMINISTRATEUR'

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/dashboard" aria-label="Gestion fournisseurs, accueil">
          <span className="brand-mark">F</span>
          <span>Fournisseurs</span>
        </NavLink>
        <nav className="main-nav" aria-label="Navigation principale">
          {commonLinks.map(([path, label]) => (
            <NavLink key={path} to={`/${path}`} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              {label}
            </NavLink>
          ))}
          {isAdmin && (
            <>
              <NavLink to="/users" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                Utilisateurs
              </NavLink>
              <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
                Historique
              </NavLink>
            </>
          )}
        </nav>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div>
            <span className="topbar-overline">Espace de gestion</span>
            <strong>{user.first_name || user.username}</strong>
          </div>
          <div className="topbar-actions">
            <span className="role-pill">{isAdmin ? 'Administrateur' : 'Acheteur'}</span>
            <Button variant="ghost" size="small" onClick={handleLogout}>Déconnexion</Button>
          </div>
        </header>
        <main className="main-content">
          {authError && <p className="inline-alert" role="status">{authError}</p>}
          <Outlet />
        </main>
      </div>
    </div>
  )
}
