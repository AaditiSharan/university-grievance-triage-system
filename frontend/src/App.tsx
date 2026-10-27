import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext.tsx';
import ProtectedRoute from './auth/ProtectedRoute.tsx';
import Login from './pages/Login.tsx';
import Register from './pages/Register.tsx';
import Submit from './pages/Submit.tsx';
import Track from './pages/Track.tsx';
import MyGrievances from './pages/MyGrievances.tsx';
import AdminDashboard from './pages/AdminDashboard.tsx';
import {
  ClipboardList,
  Search,
  LayoutDashboard,
  LogOut,
  FileText,
  GraduationCap,
} from 'lucide-react';

function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const canAccessQueue = user?.role === 'faculty' || user?.role === 'staff' || user?.role === 'admin';
  const navigate = useNavigate();

  if (!isAuthenticated) return null;

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-indigo-700 text-white'
        : 'text-indigo-100 hover:bg-indigo-700 hover:text-white'
    }`;

  return (
    <nav className="bg-indigo-600 shadow-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <GraduationCap className="h-7 w-7 text-white" />
            <span className="text-white text-lg font-bold tracking-tight">
              UniResolve <span className="text-indigo-200 font-normal">AI</span>
            </span>
          </div>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            <NavLink to="/submit" className={linkClass}>
              <FileText className="h-4 w-4" />
              <span className="hidden sm:inline">Submit</span>
            </NavLink>
            <NavLink to="/track" className={linkClass}>
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Track</span>
            </NavLink>
            <NavLink to="/my-grievances" className={linkClass}>
              <ClipboardList className="h-4 w-4" />
              <span className="hidden sm:inline">My Submissions</span>
            </NavLink>
            {canAccessQueue && (
              <NavLink to="/dashboard" className={linkClass}>
                <LayoutDashboard className="h-4 w-4" />
                <span className="hidden sm:inline">{user?.role === 'faculty' ? 'Department Queue' : 'Staff Dashboard'}</span>
              </NavLink>
            )}
          </div>

          {/* User + Logout */}
          <div className="flex items-center gap-3">
            <span className="text-indigo-200 text-sm hidden sm:block">
              {user?.username}
              {user?.role && (
                <span className="ml-1.5 badge bg-indigo-800 text-indigo-100">{user.role}</span>
              )}
            </span>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium text-indigo-100 hover:bg-indigo-700 hover:text-white transition-colors"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}

function AppRoutes() {
  const { isAuthenticated, user } = useAuth();
  const home = !isAuthenticated
    ? '/login'
    : user?.role === 'staff' || user?.role === 'faculty' || user?.role === 'admin'
      ? '/dashboard'
      : '/submit';

  return (
    <>
      <Navbar />
      <main className="min-h-[calc(100vh-64px)]">
        <Routes>
          <Route
            path="/"
            element={<Navigate to={home} replace />}
          />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/staff/login" element={<Login staffFlow />} />
          <Route path="/staff/register" element={<Register staffFlow />} />
          <Route
            path="/submit"
            element={
              <ProtectedRoute>
                <Submit />
              </ProtectedRoute>
            }
          />
          <Route
            path="/track"
            element={
              <ProtectedRoute>
                <Track />
              </ProtectedRoute>
            }
          />
          <Route
            path="/my-grievances"
            element={
              <ProtectedRoute>
                <MyGrievances />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={['faculty', 'staff', 'admin']}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute adminOnly>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
