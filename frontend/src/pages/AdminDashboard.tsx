import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { AlertCircle, CheckCircle, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';
import { getAdminGrievances, getAdminStats, submitHumanDecision } from '../api/rms.ts';
import type { Grievance, HumanDecisionPayload, StatsResponse } from '../types';

const STATUSES: HumanDecisionPayload['new_status'][] = [
  'under_review',
  'resolved',
  'closed',
  'escalated',
];

export default function AdminDashboard() {
  const [grievances, setGrievances] = useState<Grievance[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [finalCategory, setFinalCategory] = useState('');
  const [finalSubcategory, setFinalSubcategory] = useState('');
  const [finalRoute, setFinalRoute] = useState('');
  const [finalPriority, setFinalPriority] = useState('P3');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [newStatus, setNewStatus] = useState<HumanDecisionPayload['new_status']>('under_review');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selected = useMemo(
    () => grievances.find((grievance) => grievance.grievance_id === selectedId) ?? null,
    [grievances, selectedId]
  );

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, aggregate] = await Promise.all([getAdminGrievances(), getAdminStats()]);
      setGrievances(items);
      setStats(aggregate);
      setSelectedId((current) => current && items.some((item) => item.grievance_id === current)
        ? current
        : items[0]?.grievance_id ?? '');
    } catch {
      setError('Could not load the review dashboard. Confirm your administrator access and try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (!selected) return;
    setFinalCategory(selected.human_decision?.final_category ?? selected.ai_analysis?.predicted_master ?? '');
    setFinalSubcategory(selected.human_decision?.final_subcategory ?? selected.ai_analysis?.predicted_subcategory ?? '');
    setFinalRoute(selected.human_decision?.final_route ?? selected.ai_analysis?.routed_to ?? '');
    setFinalPriority(selected.human_decision?.final_priority ?? selected.ai_analysis?.priority_label ?? 'P3');
    setDecisionNotes(selected.human_decision?.decision_notes ?? '');
    setNewStatus(selected.status === 'submitted' ? 'under_review' : (
      STATUSES.includes(selected.status as HumanDecisionPayload['new_status'])
        ? selected.status as HumanDecisionPayload['new_status']
        : 'under_review'
    ));
    setNotice(null);
  }, [selected]);

  const handleReview = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: HumanDecisionPayload = {
        final_category: finalCategory.trim() || undefined,
        final_subcategory: finalSubcategory.trim() || undefined,
        final_route: finalRoute.trim() || undefined,
        final_priority: finalPriority,
        decision_notes: decisionNotes.trim() || undefined,
        new_status: newStatus,
      };
      const updated = await submitHumanDecision(selected.grievance_id, payload);
      setGrievances((current) => current.map((item) => (
        item.grievance_id === updated.grievance_id ? updated : item
      )));
      setNotice('Human review decision saved. AI recommendations remain unchanged.');
      const updatedStats = await getAdminStats();
      setStats(updatedStats);
    } catch {
      setError('The human decision was not saved. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const pending = stats?.pending_review ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Grievance Review Dashboard</h1>
          <p className="mt-1 text-gray-500">AI outputs are recommendations only. A human reviewer records every final decision.</p>
        </div>
        <button type="button" onClick={() => void loadDashboard()} disabled={loading} className="btn-secondary">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}
      {notice && (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          <CheckCircle className="h-4 w-4" /> {notice}
        </div>
      )}

      <section className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ['All grievances', stats?.total ?? 0],
          ['Awaiting human review', pending],
          ['Sensitive flags', stats?.sensitive_count ?? 0],
          ['Under review', stats?.by_status.under_review ?? 0],
          ['Resolved', stats?.by_status.resolved ?? 0],
        ].map(([label, value]) => (
          <div key={label} className="card">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
            <p className="mt-2 text-2xl font-bold text-indigo-700">{value}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <section className="card">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Submissions</h2>
          {loading && grievances.length === 0 ? (
            <div className="flex items-center gap-2 py-8 text-gray-500"><Loader2 className="h-4 w-4 animate-spin" />Loading queue…</div>
          ) : grievances.length === 0 ? (
            <p className="py-8 text-sm text-gray-500">No grievances have been submitted.</p>
          ) : (
            <div className="max-h-[70vh] space-y-2 overflow-y-auto">
              {grievances.map((grievance) => {
                const analysis = grievance.ai_analysis;
                const active = grievance.grievance_id === selectedId;
                return (
                  <button
                    type="button"
                    key={grievance.grievance_id}
                    onClick={() => setSelectedId(grievance.grievance_id)}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${active ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200 hover:bg-gray-50'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-gray-800">{grievance.grievance_id}</span>
                      <span className={`badge ${analysis?.needs_human_review && !grievance.human_decision ? 'bg-orange-100 text-orange-800' : 'bg-gray-100 text-gray-700'}`}>
                        {grievance.human_decision ? 'Reviewed' : analysis?.needs_human_review ? 'Review needed' : grievance.status}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm text-gray-600">{grievance.description}</p>
                    <p className="mt-2 text-xs text-gray-500">
                      {analysis?.priority_label ?? 'Unscored'} · {analysis?.predicted_subcategory ?? 'Unclassified'} · {grievance.status}
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section className="space-y-5">
          {!selected ? (
            <div className="card py-12 text-center text-gray-500">Select a grievance to inspect and review.</div>
          ) : (
            <>
              <article className="card">
                <div className="mb-3 flex items-center gap-2">
                  {selected.ai_analysis?.sensitivity_flag && <ShieldAlert className="h-5 w-5 text-red-600" />}
                  <h2 className="text-lg font-semibold text-gray-900">{selected.grievance_id}</h2>
                  <span className="badge bg-gray-100 text-gray-700">{selected.status}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">{selected.description}</p>
                {selected.ai_analysis && (
                  <div className="mt-4 grid gap-3 border-t border-gray-100 pt-4 sm:grid-cols-2">
                    <p className="text-sm"><span className="text-gray-500">AI category:</span> {selected.ai_analysis.predicted_master} / {selected.ai_analysis.predicted_subcategory}</p>
                    <p className="text-sm"><span className="text-gray-500">Confidence:</span> {(selected.ai_analysis.confidence * 100).toFixed(1)}%</p>
                    <p className="text-sm"><span className="text-gray-500">Priority:</span> {selected.ai_analysis.priority_label} (score {selected.ai_analysis.priority_score})</p>
                    <p className="text-sm"><span className="text-gray-500">Suggested route:</span> {selected.ai_analysis.routed_to}</p>
                    {selected.ai_analysis.sensitivity_evidence.length > 0 && (
                      <p className="sm:col-span-2 text-sm text-red-700">
                        Sensitivity evidence: {selected.ai_analysis.sensitivity_evidence.join('; ')}
                      </p>
                    )}
                    {selected.ai_analysis.priority_reasons.length > 0 && (
                      <p className="sm:col-span-2 text-sm text-gray-600">
                        Priority rationale: {selected.ai_analysis.priority_reasons.join('; ')}
                      </p>
                    )}
                  </div>
                )}
              </article>

              <form className="card space-y-4" onSubmit={handleReview}>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Human decision</h2>
                  <p className="mt-1 text-xs text-gray-500">Fields are prefilled with AI suggestions for convenience; confirm or edit them before saving.</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="text-sm font-medium text-gray-700">
                    Final category
                    <input className="input-field mt-1" value={finalCategory} onChange={(e) => setFinalCategory(e.target.value)} />
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Final subcategory
                    <input className="input-field mt-1" value={finalSubcategory} onChange={(e) => setFinalSubcategory(e.target.value)} />
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Final department
                    <input className="input-field mt-1" value={finalRoute} onChange={(e) => setFinalRoute(e.target.value)} />
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Final priority
                    <select className="input-field mt-1" value={finalPriority} onChange={(e) => setFinalPriority(e.target.value)}>
                      {['P1', 'P2', 'P3', 'P4'].map((priority) => <option key={priority}>{priority}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Status
                    <select className="input-field mt-1" value={newStatus} onChange={(e) => setNewStatus(e.target.value as HumanDecisionPayload['new_status'])}>
                      {STATUSES.map((status) => <option key={status} value={status}>{status.replace(/_/g, ' ')}</option>)}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-gray-700 sm:col-span-2">
                    Reviewer notes
                    <textarea className="input-field mt-1 min-h-24" value={decisionNotes} onChange={(e) => setDecisionNotes(e.target.value)} maxLength={4000} />
                  </label>
                </div>
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                  Save human decision
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
