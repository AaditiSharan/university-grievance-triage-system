import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { GraduationCap, AlertCircle, Loader2, CheckCircle } from 'lucide-react';
import { getDepartments, register as apiRegister } from '../api/auth.ts';

type Role = 'student' | 'faculty' | 'staff';

type RegisterProps = {
  staffFlow?: boolean;
};

export default function Register({ staffFlow = false }: RegisterProps) {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>(staffFlow ? 'staff' : 'student');
  const [department, setDepartment] = useState('');
  const [departmentOptions, setDepartmentOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let isMounted = true;

    void (async () => {
      try {
        const departments = await getDepartments();
        if (!isMounted) return;
        setDepartmentOptions(departments);
        if (role === 'student') {
          setDepartment('');
          return;
        }
        setDepartment((current) => {
          if (current && departments.includes(current)) return current;
          return departments[0] ?? '';
        });
      } catch {
        if (isMounted) {
          setDepartmentOptions([]);
          if (role !== 'student') setDepartment('');
        }
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [role]);

  const requiresDepartment = role === 'staff' || role === 'faculty';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (requiresDepartment && !department) {
      setError('Please choose a department for staff and faculty accounts.');
      return;
    }

    setLoading(true);

    try {
      await apiRegister(username, email, password, role, requiresDepartment ? department : undefined);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail ?? 'Registration failed. Please try again.');
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
            {staffFlow ? 'Staff and faculty registration' : 'Create your account'}
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">
            {staffFlow ? 'Create staff account' : 'Register'}
          </h2>

          {success && (
            <div className="mb-4 flex items-start gap-3 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
              <CheckCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>Account created! Redirecting to login…</span>
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-start gap-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!staffFlow && (
            <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700">
              Staff and faculty accounts are limited to eligible institutional email domains and do not require manual admin approval.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="reg-username" className="block text-sm font-medium text-gray-700 mb-1">
                Username
              </label>
              <input
                id="reg-username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input-field"
                placeholder="Choose a username"
              />
            </div>

            <div>
              <label htmlFor="reg-email" className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field"
                placeholder="your@university.edu"
              />
            </div>

            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                id="reg-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="At least 6 characters"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
              <div className="grid grid-cols-3 gap-2">
                {(['student', 'faculty', 'staff'] as Role[]).map((r) => (
                  <label
                    key={r}
                    className={`flex items-center justify-center p-3 border rounded-lg cursor-pointer transition-all text-sm font-medium capitalize ${
                      role === r
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-600'
                    }`}
                  >
                    <input
                      type="radio"
                      value={r}
                      checked={role === r}
                      onChange={() => {
                        setRole(r);
                        if (r === 'student') {
                          setDepartment('');
                        }
                      }}
                      className="sr-only"
                    />
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </label>
                ))}
              </div>
            </div>

            {requiresDepartment && (
              <div>
                <label htmlFor="reg-department" className="block text-sm font-medium text-gray-700 mb-1">
                  Department
                </label>
                <select
                  id="reg-department"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="input-field"
                  required={requiresDepartment}
                >
                  <option value="">Select department</option>
                  {departmentOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || success}
              className="btn-primary w-full justify-center py-3 text-base"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating account…
                </>
              ) : (
                'Create Account'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link
              to={staffFlow ? '/staff/login' : '/login'}
              className="text-indigo-600 font-medium hover:underline"
            >
              {staffFlow ? 'Staff sign in' : 'Sign in'}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
