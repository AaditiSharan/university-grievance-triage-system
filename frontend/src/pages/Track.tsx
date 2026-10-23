import { useState, type FormEvent } from 'react';
import { Search, Loader2, AlertCircle, Clock, CheckCircle, RotateCcw } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { trackGrievance } from '../api/rms.ts';
import type { Grievance, AIAnalysis } from '../types';

// ── Status Timeline ───────────────────────────────────────────────────────────
const STATUS_STEPS = ['Submitted', 'Under Review', 'Resolved'];

function StatusTimeline({ status }: { status: string }) {
  const normalised = status?.toLowerCase() ?? '';
  let activeIndex = 0;
  if (normalised.includes('review') || normalised.includes('pending') || normalised.includes('escalat')) activeIndex = 1;
  if (normalised.includes('resolv') || normalised.includes('closed') || normalised.includes('done')) activeIndex = 2;

  return (
    <div className="flex items-center gap-0">
      {STATUS_STEPS.map((step, i) => (
        <div key={step} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all ${
                i <= activeIndex
                  ? 'bg-indigo-600 border-indigo-600 text-white'
                  : 'bg-white border-gray-300 text-gray-400'
              }`}
            >
              {i < activeIndex ? (
                <CheckCircle className="h-4 w-4" />
              ) : i === activeIndex ? (
                <Clock className="h-4 w-4" />
              ) : (
                <span className="text-xs">{i + 1}</span>
              )}
            </div>
            <span
              className={`text-xs mt-1.5 font-medium whitespace-nowrap ${
                i <= activeIndex ? 'text-indigo-700' : 'text-gray-400'
              }`}
            >
              {step}
            </span>
          </div>
          {i < STATUS_STEPS.length - 1 && (
            <div
              className={`h-0.5 w-16 sm:w-24 mb-5 mx-1 transition-all ${
                i < activeIndex ? 'bg-indigo-600' : 'bg-gray-200'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ── AI Analysis Mini Panel ────────────────────────────────────────────────────
function AIAnalysisMini({ analysis }: { analysis: AIAnalysis }) {
  const conf = analysis.confidence;
  const confColor =
    conf >= 0.75
      ? 'text-green-700 bg-green-50 border-green-200'
      : conf >= 0.4
      ? 'text-yellow-700 bg-yellow-50 border-yellow-200'
      : 'text-red-700 bg-red-50 border-red-200';
  const barColor =
    conf >= 0.75 ? 'bg-green-500' : conf >= 0.4 ? 'bg-yellow-500' : 'bg-red-500';

  const priorityMap: Record<string, string> = {
    P1: 'bg-red-100 text-red-800 border-red-200',
    P2: 'bg-orange-100 text-orange-800 border-orange-200',
    P3: 'bg-blue-100 text-blue-800 border-blue-200',
    P4: 'bg-gray-100 text-gray-700 border-gray-200',
  };
  const pKey = analysis.priority_label?.slice(0, 2).toUpperCase() ?? 'P4';

  return (
    <div className="mt-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl">
      <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wide mb-3">AI Analysis</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-gray-500">Category</p>
          <p className="text-sm font-semibold text-gray-800">
            {analysis.predicted_master} › {analysis.predicted_category} › {analysis.predicted_subcategory}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Routed To</p>
          <p className="text-sm font-semibold text-gray-800">{analysis.routed_to || '—'}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Confidence</p>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${barColor}`}
                style={{ width: `${Math.min(conf * 100, 100)}%` }}
              />
            </div>
            <span className={`badge border text-xs ${confColor}`}>{(conf * 100).toFixed(0)}%</span>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500">Priority</p>
          <span className={`badge border text-xs font-bold ${priorityMap[pKey] ?? priorityMap['P4']}`}>
            {analysis.priority_label || 'N/A'}
          </span>
        </div>
      </div>
      {analysis.sensitivity_flag && (
        <div className="mt-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
          ⚠ Sensitive content detected: {analysis.sensitivity_type}
        </div>
      )}
      <p className="mt-3 text-xs text-gray-400 italic">
        AI recommendations — subject to human review.
      </p>
    </div>
  );
}

// ── Track Page ────────────────────────────────────────────────────────────────
export default function Track() {
  const [searchParams] = useSearchParams();
  const [grievanceId, setGrievanceId] = useState(searchParams.get('grievance_id') ?? '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [grievance, setGrievance] = useState<Grievance | null>(null);

  const handleTrack = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setGrievance(null);
    setLoading(true);

    try {
      const g = await trackGrievance(grievanceId.trim());
      setGrievance(g);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 404) {
          setError(`No grievance found with ID "${grievanceId}".`);
        } else {
          setError(axiosErr.response?.data?.detail ?? 'Failed to fetch grievance. Please try again.');
        }
      } else {
        setError('Unable to connect to server. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Track Submission</h1>
        <p className="text-gray-500 mt-1">Enter your Grievance ID to check the current status.</p>
      </div>

      {/* Search Form */}
      <div className="card mb-6">
        <form onSubmit={handleTrack} className="flex gap-3">
          <input
            type="text"
            value={grievanceId}
            onChange={(e) => setGrievanceId(e.target.value)}
            placeholder="e.g. GRV-20261023-00042"
            required
            className="input-field flex-1"
          />
          <button type="submit" disabled={loading} className="btn-primary px-5">
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Search className="h-4 w-4" />
                Track
              </>
            )}
          </button>
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-4">
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Grievance Detail */}
      {grievance && (
        <div className="card">
          {/* Header */}
          <div className="flex items-start justify-between mb-4 pb-4 border-b border-gray-100">
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Grievance ID</p>
              <p className="font-black text-xl text-gray-800">{grievance.grievance_id}</p>
            </div>
            <span className="badge bg-indigo-100 text-indigo-700 border border-indigo-200">
              {grievance.message_type}
            </span>
          </div>

          {/* Status timeline */}
          <div className="mb-6">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Status</p>
            <StatusTimeline status={grievance.status} />
          </div>

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <p className="text-xs text-gray-400">Submitted At</p>
              <p className="text-sm text-gray-700">
                {new Date(grievance.created_at).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Current Status</p>
              <p className="text-sm font-medium text-gray-800">{grievance.status}</p>
            </div>
          </div>

          {/* Description */}
          <div className="mb-4">
            <p className="text-xs text-gray-400 mb-1">Description</p>
            <p className="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-3 border border-gray-100">
              {grievance.description}
            </p>
          </div>

          {/* Human Decision */}
          {grievance.human_decision && (
            <div className="mb-4 p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <p className="text-xs font-semibold text-purple-600 uppercase tracking-wide mb-2">
                Human Review Decision
              </p>
              <p className="text-sm text-purple-800 font-medium">
                {grievance.human_decision.final_category || 'Reviewed'}
                {grievance.human_decision.final_subcategory && ` › ${grievance.human_decision.final_subcategory}`}
                {grievance.human_decision.final_route && ` · ${grievance.human_decision.final_route}`}
                {grievance.human_decision.final_priority && ` · ${grievance.human_decision.final_priority}`}
              </p>
              {grievance.human_decision.decision_notes && (
                <p className="text-sm text-purple-700 mt-1">{grievance.human_decision.decision_notes}</p>
              )}
              {grievance.human_decision.decided_at && (
                <p className="text-xs text-purple-400 mt-2">
                  Reviewed: {new Date(grievance.human_decision.decided_at).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {/* AI Analysis */}
          {grievance.ai_analysis && <AIAnalysisMini analysis={grievance.ai_analysis} />}
        </div>
      )}

      {/* Help */}
      {!grievance && !error && !loading && (
        <div className="text-center py-12 text-gray-400">
          <RotateCcw className="h-10 w-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Enter your Grievance ID above to track its status.</p>
        </div>
      )}
    </div>
  );
}
