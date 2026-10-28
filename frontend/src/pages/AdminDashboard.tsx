import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { AlertCircle, CheckCircle, Loader2, RefreshCw, ShieldAlert } from 'lucide-react';
import {
  getStaffGrievances,
  getStaffStats,
  requestResolutionDrafts,
  submitBulkStaffDecisions,
  submitStaffDecision,
} from '../api/rms.ts';
import { useAuth } from '../auth/AuthContext.tsx';
import type { BulkDecisionItem, Grievance, HumanDecisionPayload } from '../types';

const STATUSES: HumanDecisionPayload['new_status'][] = [
  'under_review',
  'resolved',
  'closed',
  'escalated',
];

function isSensitive(analysis: Grievance['ai_analysis']): boolean {
  return Boolean(analysis?.sensitivity_flag)
    || Boolean(analysis?.sensitivity_type && analysis.sensitivity_type.toUpperCase() !== 'NONE');
}

function isFinalized(grievance: Grievance): boolean {
  return grievance.status === 'resolved' || grievance.status === 'closed';
}

export default function AdminDashboard() {
  const [grievances, setGrievances] = useState<Grievance[]>([]);
  const [stats, setStats] = useState<{
    total: number;
    by_status: Record<string, number>;
    pending_review: number;
    sensitive_count: number;
  } | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [finalCategory, setFinalCategory] = useState('');
  const [finalSubcategory, setFinalSubcategory] = useState('');
  const [finalRoute, setFinalRoute] = useState('');
  const [finalPriority, setFinalPriority] = useState('P3');
  const [decisionNotes, setDecisionNotes] = useState('');
  const [resolutionSolution, setResolutionSolution] = useState('');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkSolutions, setBulkSolutions] = useState<Record<string, string>>({});
  const [bulkApprovals, setBulkApprovals] = useState<Record<string, boolean>>({});
  const [bulkStatus, setBulkStatus] = useState<HumanDecisionPayload['new_status']>('resolved');
  const [newStatus, setNewStatus] = useState<HumanDecisionPayload['new_status']>('under_review');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { user } = useAuth();
  const canManage = user?.role === 'staff' || user?.role === 'admin';

  const selected = useMemo(
    () => grievances.find((grievance) => grievance.grievance_id === selectedId) ?? null,
    [grievances, selectedId]
  );
  const hasSensitiveBulkSelection = selectedIds.some((id) => {
    const analysis = grievances.find((item) => item.grievance_id === id)?.ai_analysis;
    return isSensitive(analysis);
  });
  const eligibleSelectedIds = selectedIds.filter((id) => {
    const grievance = grievances.find((item) => item.grievance_id === id);
    return grievance && !isFinalized(grievance);
  });

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [items, aggregate] = await Promise.all([getStaffGrievances(), getStaffStats()]);
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
    setResolutionSolution(selected.human_decision?.resolution_solution ?? '');
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
      payload.resolution_solution = resolutionSolution.trim() || undefined;
      const updated = await submitStaffDecision(selected.grievance_id, payload);
      setGrievances((current) => current.map((item) => (
        item.grievance_id === updated.grievance_id ? updated : item
      )));
      if (isFinalized(updated)) {
        setSelectedIds((current) => current.filter((id) => id !== updated.grievance_id));
      }
      setNotice('Human review decision saved. AI recommendations remain unchanged.');
      const updatedStats = await getStaffStats();
      setStats(updatedStats);
    } catch {
      setError('The human decision was not saved. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const toggleBulkSelection = (id: string) => {
    setSelectedIds((current) => current.includes(id)
      ? current.filter((selectedId) => selectedId !== id)
      : [...current, id]);
    setBulkApprovals((current) => ({ ...current, [id]: false }));
  };

  const handleDrafts = async () => {
    if (selectedIds.length === 0) return;
    setSaving(true);
    setError(null);
    try {
      const drafts = await requestResolutionDrafts(selectedIds);
      setBulkSolutions((current) => Object.fromEntries([
        ...Object.entries(current),
        ...drafts.map(({ grievance_id, draft }) => [grievance_id, draft]),
      ]));
      setBulkApprovals({});
      setNotice('Drafts created for individual staff review. Nothing was sent or resolved.');
    } catch {
      setError('Draft generation was denied or failed. Sensitive cases require human handling.');
    } finally {
      setSaving(false);
    }
  };

  const handleBulkReview = async () => {
    const items: BulkDecisionItem[] = eligibleSelectedIds.map((id) => {
      const grievance = grievances.find((item) => item.grievance_id === id);
      return {
        grievance_id: id,
        final_category: grievance?.human_decision?.final_category ?? grievance?.ai_analysis?.predicted_master,
        final_subcategory: grievance?.human_decision?.final_subcategory ?? grievance?.ai_analysis?.predicted_subcategory,
        final_route: grievance?.human_decision?.final_route ?? grievance?.ai_analysis?.routed_to,
        final_priority: grievance?.human_decision?.final_priority ?? grievance?.ai_analysis?.priority_label,
        decision_notes: grievance?.human_decision?.decision_notes,
        resolution_solution: bulkSolutions[id],
        new_status: bulkStatus,
        approved: Boolean(bulkApprovals[id]),
      };
    });
    if (items.length === 0 || items.some((item) => !item.approved || !item.resolution_solution?.trim())) {
      setError('Review and approve an individual solution for every selected grievance before applying the bulk action.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await submitBulkStaffDecisions(items);
      setGrievances((current) => current.map((item) =>
        updated.find((entry) => entry.grievance_id === item.grievance_id) ?? item
      ));
      setSelectedIds([]);
      setBulkApprovals({});
      setNotice(`${updated.length} individually approved decisions saved.`);
      setStats(await getStaffStats());
    } catch {
      setError('The bulk action was not saved. Confirm each case is authorized and try again.');
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
          <p className="mt-1 text-xs text-gray-500">
            {user?.role === 'faculty' ? `Read-only department queue${user.department ? `: ${user.department}` : ''}` : `Authorized department: ${user?.department ?? 'All departments'}`}
          </p>
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
                  <div key={grievance.grievance_id} className={`rounded-lg border p-3 ${active ? 'border-indigo-400 bg-indigo-50' : 'border-gray-200'}`}>
                    <div className="flex items-center gap-2">
                      {canManage && !isFinalized(grievance) && <input
                        aria-label={`Select ${grievance.grievance_id} for bulk resolution`}
                        type="checkbox"
                        checked={selectedIds.includes(grievance.grievance_id)}
                        onChange={() => toggleBulkSelection(grievance.grievance_id)}
                      />}
                      <button type="button" onClick={() => setSelectedId(grievance.grievance_id)} className="min-w-0 flex-1 text-left">
                      <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-gray-800">{grievance.grievance_id}</span>
                      <span className={`badge ${analysis?.needs_human_review && !grievance.human_decision ? 'bg-orange-100 text-orange-800' : 'bg-gray-100 text-gray-700'}`}>
                        {grievance.human_decision ? 'Reviewed' : analysis?.needs_human_review ? 'Review needed' : grievance.status}
                      </span>
                      </span>
                      <span className="mt-1 block line-clamp-2 text-sm text-gray-600">{grievance.description}</span>
                      <span className="mt-2 block text-xs text-gray-500">
                      {analysis?.priority_label ?? 'Unscored'} · {analysis?.predicted_subcategory ?? 'Unclassified'} · {grievance.status}
                      </span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {canManage && eligibleSelectedIds.length > 0 && (
            <div className="mt-4 border-t border-gray-200 pt-4">
              <h3 className="font-semibold">Bulk resolution ({eligibleSelectedIds.length})</h3>
              <p className="mt-1 text-xs text-gray-500">Drafts are never sent automatically. Review and approve each case below.</p>
              {hasSensitiveBulkSelection && <p role="alert" className="mt-2 text-xs text-red-700">Sensitive cases cannot receive AI-assisted drafts. Handle them directly as a human reviewer.</p>}
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" disabled={saving || hasSensitiveBulkSelection} onClick={() => void handleDrafts()} className="btn-secondary">Draft non-sensitive responses</button>
                <button type="button" onClick={() => setBulkSolutions(Object.fromEntries(eligibleSelectedIds.map((id) => [id, resolutionSolution])))} className="btn-secondary">Apply staff solution</button>
              </div>
              <label className="mt-3 block text-sm">Bulk status
                <select className="input-field mt-1" value={bulkStatus} onChange={(event) => setBulkStatus(event.target.value as HumanDecisionPayload['new_status'])}>
                  {STATUSES.map((status) => <option key={status} value={status}>{status.replace(/_/g, ' ')}</option>)}
                </select>
              </label>
              <div className="mt-3 space-y-3">
                {eligibleSelectedIds.map((id) => (
                  <div key={id} className="rounded-lg bg-gray-50 p-3">
                    <label className="block text-sm font-medium">{id} — individual solution
                      <textarea className="input-field mt-1 min-h-20" value={bulkSolutions[id] ?? ''} onChange={(event) => {
                        setBulkSolutions((current) => ({ ...current, [id]: event.target.value }));
                        setBulkApprovals((current) => ({ ...current, [id]: false }));
                      }} />
                    </label>
                    <label className="mt-2 flex items-center gap-2 text-xs text-gray-700">
                      <input type="checkbox" checked={Boolean(bulkApprovals[id])} onChange={(event) => setBulkApprovals((current) => ({ ...current, [id]: event.target.checked }))} />
                      I reviewed and approve this individual decision
                    </label>
                  </div>
                ))}
              </div>
              <button type="button" disabled={saving} onClick={() => void handleBulkReview()} className="btn-primary mt-3">Apply approved decisions</button>
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
                  {isSensitive(selected.ai_analysis) && <ShieldAlert className="h-5 w-5 text-red-600" />}
                  <h2 className="text-lg font-semibold text-gray-900">{selected.grievance_id}</h2>
                  <span className="badge bg-gray-100 text-gray-700">{selected.status}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">{selected.description}</p>
                {selected.ai_analysis && (
                  <div className="mt-4 grid gap-3 border-t border-gray-100 pt-4 sm:grid-cols-2">
                    <p className="text-sm"><span className="text-gray-500">AI category:</span> {selected.ai_analysis.predicted_master} / {selected.ai_analysis.predicted_subcategory}</p>
                    <p className="text-sm"><span className="text-gray-500">Sensitivity:</span> {isSensitive(selected.ai_analysis) ? `Flagged (${selected.ai_analysis.sensitivity_type})` : 'Not flagged'}</p>
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

              {canManage && !isFinalized(selected) ? <form className="card space-y-4" onSubmit={handleReview}>
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
                  <label className="text-sm font-medium text-gray-700 sm:col-span-2">
                    Staff-written resolution solution
                    <textarea className="input-field mt-1 min-h-24" value={resolutionSolution} onChange={(e) => setResolutionSolution(e.target.value)} maxLength={10000} />
                  </label>
                </div>
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle className="h-4 w-4" />}
                  Save human decision
                </button>
              </form> : (
                <article className="card">
                  <h2 className="text-lg font-semibold">Human decision</h2>
                  <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    <div><dt className="text-gray-500">Final category</dt><dd className="font-medium text-gray-800">{selected.human_decision?.final_category || 'Not recorded'}</dd></div>
                    <div><dt className="text-gray-500">Final subcategory</dt><dd className="font-medium text-gray-800">{selected.human_decision?.final_subcategory || 'Not recorded'}</dd></div>
                    <div><dt className="text-gray-500">Department / route</dt><dd className="font-medium text-gray-800">{selected.human_decision?.final_route || 'Not recorded'}</dd></div>
                    <div><dt className="text-gray-500">Final priority</dt><dd className="font-medium text-gray-800">{selected.human_decision?.final_priority || 'Not recorded'}</dd></div>
                    <div><dt className="text-gray-500">Status</dt><dd className="font-medium text-gray-800">{selected.status.replace(/_/g, ' ')}</dd></div>
                    <div><dt className="text-gray-500">Resolution time</dt><dd className="font-medium text-gray-800">{selected.human_decision?.decided_at ? new Date(selected.human_decision.decided_at).toLocaleString() : 'Not recorded'}</dd></div>
                  </dl>
                  <h3 className="mt-4 text-sm font-semibold">Reviewer notes</h3>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{selected.human_decision?.decision_notes || 'No reviewer notes recorded.'}</p>
                  <h3 className="mt-4 text-sm font-semibold">Resolution</h3>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{selected.human_decision?.resolution_solution || 'No resolution recorded.'}</p>
                </article>
              )}
              <article className="card">
                <h2 className="text-lg font-semibold">Status history</h2>
                <ol className="mt-3 space-y-2 text-sm">
                  {(selected.status_history ?? []).map((entry, index) => (
                    <li key={`${entry.changed_at}-${index}`} className="text-gray-600">
                      {entry.previous_status ? `${entry.previous_status} → ` : ''}{entry.new_status} · {entry.changed_by} · {new Date(entry.changed_at).toLocaleString()}
                    </li>
                  ))}
                </ol>
              </article>
              <article className="card">
                <h2 className="text-lg font-semibold">Review audit</h2>
                <ol className="mt-3 space-y-2 text-sm">
                  {(selected.audit_events ?? []).map((event, index) => (
                    <li key={`${event.timestamp}-${index}`} className="text-gray-600">
                      {event.action.replace(/_/g, ' ').toLowerCase()} · {event.actor} · {new Date(event.timestamp).toLocaleString()}
                    </li>
                  ))}
                </ol>
              </article>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
