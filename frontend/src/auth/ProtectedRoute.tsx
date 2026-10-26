import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext.tsx';
import type { ReactNode } from 'react';

interface Props {
  children: ReactNode;
  adminOnly?: boolean;
  allowedRoles?: Array<'student' | 'faculty' | 'staff' | 'admin'>;
}

export default function ProtectedRoute({ children, adminOnly = false, allowedRoles }: Props) {
  const { isAuthenticated, isAdmin, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (adminOnly && !isAdmin) {
    return <Navigate to="/submit" replace />;
  }
  if (allowedRoles && (!user || !allowedRoles.includes(user.role))) {
    return <Navigate to="/submit" replace />;
  }

  return <>{children}</>;
}
