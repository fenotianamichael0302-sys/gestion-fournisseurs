import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

export default function RoleRoute({ allowedRoles }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return allowedRoles.includes(user.role) ? <Outlet /> : <Navigate to="/dashboard" replace />
}
