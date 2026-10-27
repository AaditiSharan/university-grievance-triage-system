import { useState, type FormEvent } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { GraduationCap, AlertCircle, Loader2 } from 'lucide-react';
import { login as apiLogin, getMe } from '../api/auth.ts';
import { useAuth } from '../auth/AuthContext.tsx';

type LoginProps = {
  staffFlow?: boolean;
};

export default function Login({ staffFlow = false }: LoginProps) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { access_token } = await apiLogin(username, password);
      // Temporarily store token so getMe() interceptor can use it
      localStorage.setItem('token', access_token);
      const user = await getMe();
      login(access_token, user);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      localStorage.removeItem('token');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        if (axiosErr.response?.status === 401) {
          setError('Invalid username or password.');
        } else {
          setError(axiosErr.response?.data?.detail ?? 'Login failed. Please try again.');
        }
      } else {
        setError('Unable to connect to server. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-blue-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="bg-indigo-600 rounded-2xl p-4 shadow-lg">
              <GraduationCap className="h-10 w-10 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">UniResolve AI</h1>
          <p className="mt-2 text-gray-500">
            {staffFlow ? 'Staff and faculty access portal' : 'University Grievance & Resolution Portal'}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">
            {staffFlow ? 'Staff sign in' : 'Sign in to your account'}
          </h2>

          {error && (
            <div className="mb-4 flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                placeholder="Enter your username"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="Enter your password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3 text-base"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            {staffFlow ? 'Need a staff account?' : "Don't have an account?"}{' '}
            <Link
              to={staffFlow ? '/staff/register' : '/register'}
              className="text-indigo-600 font-medium hover:underline"
            >
              {staffFlow ? 'Create staff account' : 'Register here'}
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-gray-400">
          Powered by AI-assisted triage &amp; routing
        </p>
      </div>
    </div>
  );
}
