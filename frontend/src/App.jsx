import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/useAuth'
import AppLayout from './components/AppLayout'
import DashboardPage from './pages/DashboardPage'
import DeliveriesPage from './pages/DeliveriesPage'
import EvaluationsPage from './pages/EvaluationsPage'
import QuotesPage from './pages/QuotesPage'
import HistoryPage from './pages/HistoryPage'
import InvoicesPage from './pages/InvoicesPage'
import LoginPage from './pages/LoginPage'
import OrdersPage from './pages/OrdersPage'
import PaymentsPage from './pages/PaymentsPage'
import ReportsPage from './pages/ReportsPage'
import SupplierDetailPage from './pages/SupplierDetailPage'
import SuppliersPage from './pages/SuppliersPage'
import UsersPage from './pages/UsersPage'
import PrivateRoute from './routes/PrivateRoute'
import RoleRoute from './routes/RoleRoute'

function App() {
  const { isLoading } = useAuth()

  if (isLoading) {
    return <main className="app-loading" aria-live="polite">Chargement de votre espace…</main>
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<PrivateRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/suppliers/:supplierId" element={<SupplierDetailPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/deliveries" element={<DeliveriesPage />} />
          <Route path="/evaluations" element={<EvaluationsPage />} />
          <Route path="/quotes" element={<QuotesPage />} />
          <Route path="/invoices" element={<InvoicesPage />} />
          <Route path="/payments" element={<PaymentsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route element={<RoleRoute allowedRoles={['ADMINISTRATEUR']} />}>
            <Route path="/users" element={<UsersPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
