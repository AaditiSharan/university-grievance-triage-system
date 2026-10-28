import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ClipboardList, Loader2, RefreshCw } from 'lucide-react';
import { getMyGrievances } from '../api/rms.ts';
import type { Grievance } from '../types';

function displayDate(value: string): string {
  return new Date(value).toLocaleString();
}

export default function MyGrievances() {
  const [grievances, setGrievances] = useState<Grievance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadGrievances = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setGrievances(await getMyGrievances());
    } catch {
      setError('Could not load your submissions. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGrievances();
  }, [loadGrievances]);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Submissions</h1>
          <p className="text-gray-500 mt-1">Track progress and review AI recommendations for your grievances.</p>
        </div>
        <button type="button" onClick={() => void loadGrievances()} disabled={loading} className="btn-secondary">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {loading && grievances.length === 0 ? (
        <div className="card flex items-center justify-center gap-2 py-12 text-gray-500">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading submissions…
        </div>
      ) : grievances.length === 0 ? (
        <div className="card py-12 text-center">
          <ClipboardList className="mx-auto mb-3 h-10 w-10 text-gray-300" />
          <p className="font-medium text-gray-700">No submissions yet</p>
          <p className="mt-1 text-sm text-gray-500">Your submitted grievances will appear here.</p>
          <Link className="btn-primary mt-5 inline-flex" to="/submit">Submit a grievance</Link>
        </div>
      ) : (
        <div className="space-y-4">
          {grievances.map((grievance) => {
            const analysis = grievance.ai_analysis;
            return (
              <article key={grievance.grievance_id} className="card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link
                      to={`/track?grievance_id=${encodeURIComponent(grievance.grievance_id)}`}
                      className="font-semibold text-indigo-700 hover:underline"
                    >
                      {grievance.grievance_id}
                    </Link>
                    <p className="mt-1 text-xs text-gray-500">
                      {grievance.message_type} · {displayDate(grievance.created_at)}
                    </p>
                  </div>
                  <span className="badge border border-indigo-200 bg-indigo-50 text-indigo-700">
                    {grievance.status.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="mt-4 text-sm leading-relaxed text-gray-700">{grievance.description}</p>
                <section className="mt-3 rounded-lg border border-purple-200 bg-purple-50 p-3">
                  <h2 className="text-sm font-semibold text-purple-800">Resolution from Staff</h2>
                  {grievance.human_decision?.resolution_solution?.trim() ? (
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-purple-900">
                      {grievance.human_decision.resolution_solution}
                    </p>
                  ) : grievance.status !== 'resolved' && grievance.status !== 'closed' ? (
                    <p className="mt-2 text-sm text-purple-700">Awaiting staff resolution</p>
                  ) : null}
                </section>
                {analysis && (
                  <div className="mt-4 grid gap-3 border-t border-gray-100 pt-4 sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-gray-500">AI category suggestion</p>
                      <p className="text-sm font-medium text-gray-800">
                        {analysis.predicted_master} / {analysis.predicted_subcategory}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Priority suggestion</p>
                      <p className="text-sm font-medium text-gray-800">{analysis.priority_label}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Department suggestion</p>
                      <p className="text-sm font-medium text-gray-800">{analysis.routed_to}</p>
                    </div>
                    <p className="sm:col-span-3 text-xs text-gray-500">
                      AI output is advisory; final handling remains with a human reviewer.
                    </p>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
