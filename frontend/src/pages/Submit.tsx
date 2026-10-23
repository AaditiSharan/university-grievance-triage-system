import { useState, type FormEvent, type ChangeEvent } from 'react';
import {
  Send,
  Copy,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Shield,
  Star,
  Loader2,
  AlertCircle,
  Info,
} from 'lucide-react';
import { submitGrievance } from '../api/rms.ts';
import type { GrievanceSubmit, AIAnalysis, SubmitResponse } from '../types';

// ── Category Tree ─────────────────────────────────────────────────────────────
const CATEGORY_TREE: Record<string, Record<string, string[]>> = {
  Academics: {
    Timetable: ['Section Timetable Not Updated', 'Other Timetable Issue'],
    Attendance: ['Attendance Shortage Condonation', 'Attendance Not Marked', 'Other Attendance Issue'],
    'Course Registration': ['Course Not Available', 'Registration Error', 'Other Course Registration Issue'],
    'Online Classes': ['Link Not Working', 'Recording Not Available', 'Other Online Class Issue'],
  },
  Examination: {
    Results: ['Result Not Declared', 'Marks Mismatch', 'Result Error'],
    'Re-evaluation': ['Re-evaluation Request', 'Re-evaluation Status'],
    'Admit Card': ['Admit Card Not Generated', 'Admit Card Error'],
    Datesheet: ['Datesheet Not Published', 'Datesheet Error'],
  },
  Finance: {
    Fee: ['Fee Payment Not Reflected', 'Fee Receipt Request', 'Refund Request'],
    Scholarship: ['Scholarship Not Credited', 'Scholarship Status', 'Scholarship Application Issue'],
  },
  Hostel: {
    Maintenance: ['Room Maintenance', 'Common Area Issue', 'Electrical Issue', 'Plumbing Issue'],
    Mess: ['Food Quality Issue', 'Mess Timing Issue', 'Mess Bill Issue'],
  },
  'IT Services': {
    Network: ['Wi-Fi Not Working', 'Internet Speed Issue', 'Network Access Issue'],
    UMS: ['UMS Login Issue', 'UMS Data Error', 'UMS Feature Request'],
  },
  Administration: {
    Documents: ['Bonafide Certificate Request', 'ID Card Issue', 'Migration Certificate', 'Other Document'],
    Transport: ['Bus Route or Timing', 'Bus Pass Issue', 'Vehicle Complaint'],
    Library: ['Book Not Available', 'Library Card Issue', 'Library Fine Issue'],
  },
  'Events & Activities': {
    'Duty Leave': ['Duty Leave Not Approved', 'Duty Leave Document Issue'],
    Events: ['Event Permission Issue', 'Event Participation Issue'],
  },
  'Student Welfare': {
    Ragging: ['Ragging Complaint'],
    Harassment: ['Harassment Complaint'],
    'Threat or Violence': ['Threat Complaint', 'Violence Complaint'],
    'Mental Health': ['Mental Health Concern', 'Counselling Request'],
    'Medical Emergency': ['Medical Emergency'],
  },
  'Feedback & Suggestions': {
    'Positive Feedback': ['Positive Feedback'],
    'General Suggestion': ['General Suggestion'],
  },
};

const MESSAGE_TYPES = [
  'Grievance',
  'Assistance',
  'Enquiry',
  'Query',
  'Request',
  'Feedback',
  'Positive Feedback',
] as const;

type MsgType = (typeof MESSAGE_TYPES)[number];

// ── Helpers ───────────────────────────────────────────────────────────────────

function confidenceColor(conf: number): string {
  if (conf >= 0.75) return 'text-green-700 bg-green-50 border-green-200';
  if (conf >= 0.4) return 'text-yellow-700 bg-yellow-50 border-yellow-200';
  return 'text-red-700 bg-red-50 border-red-200';
}

function confidenceBarColor(conf: number): string {
  if (conf >= 0.75) return 'bg-green-500';
  if (conf >= 0.4) return 'bg-yellow-500';
  return 'bg-red-500';
}

function priorityBadge(label: string) {
  const map: Record<string, string> = {
    P1: 'bg-red-100 text-red-800 border-red-200',
    P2: 'bg-orange-100 text-orange-800 border-orange-200',
    P3: 'bg-blue-100 text-blue-800 border-blue-200',
    P4: 'bg-gray-100 text-gray-700 border-gray-200',
  };
  const key = label?.toUpperCase().startsWith('P') ? label.slice(0, 2).toUpperCase() : 'P4';
  return map[key] ?? map['P4'];
}

function sensitivityBannerColor(type: string): string {
  const upper = type?.toUpperCase() ?? '';
  if (upper.includes('SAFETY') || upper.includes('MENTAL') || upper.includes('RAGGING') || upper.includes('VIOLENCE')) {
    return 'bg-red-50 border-red-300 text-red-800';
  }
  if (upper.includes('DEADLINE') || upper.includes('CONFIDENTIAL') || upper.includes('HARASSMENT')) {
    return 'bg-orange-50 border-orange-300 text-orange-800';
  }
  return 'bg-yellow-50 border-yellow-300 text-yellow-800';
}

// ── AI Analysis Panel ─────────────────────────────────────────────────────────
function AIAnalysisPanel({ analysis }: { analysis: AIAnalysis }) {
  const [activeTab, setActiveTab] = useState<
    'classification' | 'sensitivity' | 'priority' | 'completeness' | 'incident'
  >('classification');

  const tabs = [
    { id: 'classification', label: 'Classification' },
    { id: 'sensitivity', label: 'Sensitivity' },
    { id: 'priority', label: 'Priority & Routing' },
    { id: 'completeness', label: 'Completeness' },
    { id: 'incident', label: 'Incident Match' },
  ] as const;

  const conf = analysis.confidence;

  return (
    <div className="mt-6 border border-indigo-200 rounded-xl overflow-hidden shadow-sm">
      {/* Tab bar */}
      <div className="flex overflow-x-auto bg-indigo-50 border-b border-indigo-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? 'bg-white border-b-2 border-indigo-600 text-indigo-700'
                : 'text-indigo-500 hover:text-indigo-700'
            }`}
          >
            {tab.label}
            {tab.id === 'sensitivity' && analysis.sensitivity_flag && (
              <span className="ml-1.5 inline-block w-2 h-2 rounded-full bg-red-500" />
            )}
            {tab.id === 'incident' && analysis.incident_found && (
              <span className="ml-1.5 inline-block w-2 h-2 rounded-full bg-indigo-500" />
            )}
          </button>
        ))}
      </div>

      <div className="p-5 bg-white">
        {/* CLASSIFICATION TAB */}
        {activeTab === 'classification' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { label: 'Master Category', value: analysis.predicted_master },
                { label: 'Category', value: analysis.predicted_category },
                { label: 'Subcategory', value: analysis.predicted_subcategory },
              ].map((item) => (
                <div key={item.label} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                  <p className="text-xs text-gray-500 mb-0.5">{item.label}</p>
                  <p className="text-sm font-semibold text-gray-800">{item.value || '—'}</p>
                </div>
              ))}
            </div>

            {/* Confidence */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-gray-700">Confidence</span>
                <span
                  className={`badge border text-xs font-bold ${confidenceColor(conf)}`}
                >
                  {(conf * 100).toFixed(1)}%{' '}
                  {conf >= 0.75 ? '✓ High' : conf >= 0.4 ? '~ Medium' : '⚠ Low'}
                </span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${confidenceBarColor(conf)}`}
                  style={{ width: `${Math.min(conf * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* Top classes */}
            {analysis.top_classes?.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Top Predictions</p>
                <div className="space-y-2">
                  {analysis.top_classes.slice(0, 3).map((cls, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs text-gray-500 w-4">{i + 1}</span>
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-400 rounded-full"
                          style={{ width: `${cls.probability * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-700 min-w-[3.5rem] text-right">
                        {(cls.probability * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-gray-600 truncate max-w-[140px]">{cls.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {analysis.classifier_explanation?.length > 0 && (
              <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-3">
                <p className="text-sm font-medium text-indigo-800">Classification evidence</p>
                <p className="mt-1 text-xs text-indigo-700">
                  TF-IDF terms contributing to the leading category: {analysis.classifier_explanation.join(', ')}
                </p>
              </div>
            )}
            {!analysis.classifier_available && (
              <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800">
                The trained classifier is unavailable. This submission is marked for human review.
              </div>
            )}

            {/* Baseline vs model */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                <p className="text-xs text-gray-500 mb-0.5">Baseline Prediction</p>
                <p className="text-sm text-gray-700">{analysis.baseline_prediction || '—'}</p>
              </div>
              <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100">
                <p className="text-xs text-indigo-500 mb-0.5">AI Model Prediction</p>
                <p className="text-sm text-indigo-700 font-medium">{analysis.model_prediction || '—'}</p>
              </div>
            </div>
            {analysis.baseline_keywords?.length > 0 && (
              <p className="text-xs text-gray-500">
                Baseline keyword evidence: {analysis.baseline_keywords.join(', ')}
              </p>
            )}
          </div>
        )}

        {/* SENSITIVITY TAB */}
        {activeTab === 'sensitivity' && (
          <div className="space-y-4">
            {analysis.sensitivity_flag ? (
              <>
                <div className={`p-4 rounded-lg border flex items-start gap-3 ${sensitivityBannerColor(analysis.sensitivity_type)}`}>
                  <Shield className="h-5 w-5 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold">Sensitive Content Detected</p>
                    <p className="text-sm mt-0.5">Type: <strong>{analysis.sensitivity_type}</strong></p>
                  </div>
                </div>
                {analysis.sensitivity_evidence?.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Matched Evidence</p>
                    <div className="flex flex-wrap gap-2">
                      {analysis.sensitivity_evidence.map((ev, i) => (
                        <span key={i} className="px-2 py-1 bg-red-50 border border-red-200 text-red-700 rounded text-xs font-mono">
                          {ev}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
                <CheckCheck className="h-5 w-5" />
                <span className="font-medium">No sensitive content detected.</span>
              </div>
            )}
          </div>
        )}

        {/* PRIORITY & ROUTING TAB */}
        {activeTab === 'priority' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-1.5">Priority</p>
                <span className={`badge border text-sm font-bold px-3 py-1 ${priorityBadge(analysis.priority_label)}`}>
                  {analysis.priority_label || 'N/A'}
                </span>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1.5">Routed To</p>
                <p className="text-sm font-semibold text-gray-800">{analysis.routed_to || '—'}</p>
                <p className="mt-1 text-xs text-gray-500">Routing basis: {analysis.routing_basis}</p>
            </div>
              </div>

            <div>
              <p className="text-sm font-medium text-gray-700 mb-1.5">Human Review Required</p>
              <div className={`flex items-center gap-2 text-sm ${analysis.needs_human_review ? 'text-orange-700' : 'text-green-700'}`}>
                {analysis.needs_human_review ? (
                  <AlertTriangle className="h-4 w-4" />
                ) : (
                  <CheckCheck className="h-4 w-4" />
                )}
                <span>
                  {analysis.needs_human_review
                    ? 'Yes — elevated human review required'
                    : 'No elevated review flag — final handling still requires a human decision'}
                </span>
              </div>
              {analysis.review_reasons?.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {analysis.review_reasons.map((r, i) => (
                    <li key={i} className="text-xs text-orange-600 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-400 flex-shrink-0" />
                      {r}
                    </li>
                  ))}
                </ul>
              )}
              {analysis.priority_reasons?.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-gray-100 pt-3">
                  {analysis.priority_reasons.map((reason, i) => (
                    <li key={i} className="text-xs text-gray-600">{reason}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* COMPLETENESS TAB */}
        {activeTab === 'completeness' && (
          <div className="space-y-4">
            <div className={`flex items-center gap-3 p-3 rounded-lg border ${analysis.is_complete ? 'bg-green-50 border-green-200 text-green-700' : 'bg-yellow-50 border-yellow-200 text-yellow-700'}`}>
              {analysis.is_complete ? (
                <CheckCheck className="h-5 w-5 flex-shrink-0" />
              ) : (
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
              )}
              <span className="font-medium">
                {analysis.is_complete ? 'Submission appears complete.' : 'Some information may be missing.'}
              </span>
            </div>
            {analysis.completeness_issues?.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Suggestions</p>
                <ul className="space-y-2">
                  {analysis.completeness_issues.map((issue, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                      <Info className="h-4 w-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* INCIDENT MATCH TAB */}
        {activeTab === 'incident' && (
          <div className="space-y-4">
            {analysis.incident_found ? (
              <>
                <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-lg">
                  <p className="text-xs text-indigo-500 mb-0.5">Matched Incident</p>
                  <p className="font-semibold text-indigo-800">{analysis.incident_id}</p>
                  <p className="text-sm text-indigo-600 mt-0.5">{analysis.incident_title}</p>
                </div>
                {analysis.reply_template && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Suggested Reply Template</p>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap font-mono">
                      {analysis.reply_template}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center gap-3 p-4 bg-gray-50 border border-gray-200 rounded-lg text-gray-600">
                <Info className="h-5 w-5 flex-shrink-0" />
                <span>No matching incident found in the knowledge base.</span>
              </div>
            )}
          </div>
        )}

        {/* Disclaimer */}
        <p className="mt-5 pt-4 border-t border-gray-100 text-xs text-gray-400 italic">
          These are AI recommendations. A human reviewer will make the final decision.
        </p>
      </div>
    </div>
  );
}

// ── Success Card ───────────────────────────────────────────────────────────────
function SuccessCard({ result }: { result: SubmitResponse }) {
  const [copied, setCopied] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(result.grievance_id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="mt-6 animate-in">
      <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
        <div className="flex justify-center mb-3">
          <div className="bg-green-100 rounded-full p-3">
            <CheckCheck className="h-8 w-8 text-green-600" />
          </div>
        </div>
        <h3 className="text-lg font-bold text-green-800 mb-1">Submission Received!</h3>
        <p className="text-sm text-green-600 mb-4">
          Your submission has been received and is being triaged by our AI system.
        </p>

        {/* Grievance ID */}
        <div className="inline-flex items-center gap-3 bg-white border-2 border-green-300 rounded-lg px-5 py-3 mb-4">
          <span className="text-2xl font-black text-gray-800 tracking-wide">
            {result.grievance_id}
          </span>
          <button
            onClick={handleCopy}
            title="Copy ID"
            className="text-gray-400 hover:text-indigo-600 transition-colors"
          >
            {copied ? <CheckCheck className="h-5 w-5 text-green-600" /> : <Copy className="h-5 w-5" />}
          </button>
        </div>

        <div className="flex justify-center">
          <button
            onClick={() => setShowAnalysis((v) => !v)}
            className="btn-secondary text-sm"
          >
            {showAnalysis ? (
              <>
                <ChevronUp className="h-4 w-4" /> Hide AI Analysis
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4" /> View AI Analysis
              </>
            )}
          </button>
        </div>
      </div>

      {showAnalysis && result.ai_analysis && (
        <AIAnalysisPanel analysis={result.ai_analysis} />
      )}
    </div>
  );
}

// ── Main Submit Page ──────────────────────────────────────────────────────────
export default function Submit() {
  const [msgType, setMsgType] = useState<MsgType>('Grievance');
  const [selectedMaster, setSelectedMaster] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedSubcategory, setSelectedSubcategory] = useState('');
  const [description, setDescription] = useState('');
  const [language, setLanguage] = useState('English');
  const [section, setSection] = useState('');
  const [hostelBlock, setHostelBlock] = useState('');
  const [courseCode, setCourseCode] = useState('');
  const [eventName, setEventName] = useState('');
  const [contactNo, setContactNo] = useState('');
  const [urgentDeadline, setUrgentDeadline] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SubmitResponse | null>(null);

  const masters = Object.keys(CATEGORY_TREE);
  const categories = selectedMaster ? Object.keys(CATEGORY_TREE[selectedMaster] ?? {}) : [];
  const subcategories =
    selectedMaster && selectedCategory
      ? (CATEGORY_TREE[selectedMaster]?.[selectedCategory] ?? [])
      : [];

  const handleMasterChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setSelectedMaster(e.target.value);
    setSelectedCategory('');
    setSelectedSubcategory('');
  };

  const handleCategoryChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setSelectedCategory(e.target.value);
    setSelectedSubcategory('');
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (description.trim().length < 50) {
      setError('Please provide at least 50 characters in the description.');
      return;
    }

    setLoading(true);

    const payload: GrievanceSubmit = {
      message_type: msgType,
      description: description.trim(),
      language,
      ...(selectedMaster && { selected_master: selectedMaster }),
      ...(selectedCategory && { selected_category: selectedCategory }),
      ...(selectedSubcategory && { selected_subcategory: selectedSubcategory }),
      ...(section && { section }),
      ...(hostelBlock && { hostel_block: hostelBlock }),
      ...(courseCode && { course_code: courseCode }),
      ...(eventName && { event_name: eventName }),
      ...(contactNo && { contact_no: contactNo }),
      urgent_deadline: urgentDeadline,
    };

    try {
      const res = await submitGrievance(payload);
      setResult(res);
      // Scroll to result
      setTimeout(() => {
        document.getElementById('submit-result')?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail ?? 'Submission failed. Please try again.');
      } else {
        setError('Unable to connect to server. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleNewSubmission = () => {
    setResult(null);
    setDescription('');
    setSelectedMaster('');
    setSelectedCategory('');
    setSelectedSubcategory('');
    setSection('');
    setHostelBlock('');
    setCourseCode('');
    setEventName('');
    setContactNo('');
    setUrgentDeadline(false);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">New Submission</h1>
        <p className="text-gray-500 mt-1">
          Submit a grievance, query, or request. Our AI will triage and route it automatically.
        </p>
      </div>

      {!result ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Section 1: Submission Type */}
          <div className="card">
            <h2 className="text-base font-semibold text-gray-800 mb-4">
              1. Submission Type
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
              {MESSAGE_TYPES.map((type) => (
                <label
                  key={type}
                  className={`flex items-center justify-center p-3 border rounded-lg cursor-pointer text-sm font-medium text-center transition-all ${
                    msgType === type
                      ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                      : 'border-gray-200 hover:border-gray-300 text-gray-600'
                  }`}
                >
                  <input
                    type="radio"
                    value={type}
                    checked={msgType === type}
                    onChange={() => setMsgType(type)}
                    className="sr-only"
                  />
                  {type === 'Positive Feedback' ? (
                    <span className="flex flex-col items-center gap-1">
                      <Star className="h-4 w-4" />
                      Positive Feedback
                    </span>
                  ) : (
                    type
                  )}
                </label>
              ))}
            </div>
          </div>

          {/* Section 2: Classification */}
          <div className="card">
            <h2 className="text-base font-semibold text-gray-800 mb-1">
              2. Classification{' '}
              <span className="text-xs font-normal text-gray-400">(optional — AI will decide if left blank)</span>
            </h2>
            <p className="text-xs text-gray-400 mb-4">
              Use dropdowns to help the AI. Leave blank for fully automatic classification.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Master Category</label>
                <div className="relative">
                  <select
                    value={selectedMaster}
                    onChange={handleMasterChange}
                    className="input-field appearance-none pr-8"
                  >
                    <option value="">Auto-detect</option>
                    {masters.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <div className="relative">
                  <select
                    value={selectedCategory}
                    onChange={handleCategoryChange}
                    disabled={!selectedMaster}
                    className="input-field appearance-none pr-8 disabled:bg-gray-50 disabled:text-gray-400"
                  >
                    <option value="">Auto-detect</option>
                    {categories.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subcategory</label>
                <div className="relative">
                  <select
                    value={selectedSubcategory}
                    onChange={(e) => setSelectedSubcategory(e.target.value)}
                    disabled={!selectedCategory}
                    className="input-field appearance-none pr-8 disabled:bg-gray-50 disabled:text-gray-400"
                  >
                    <option value="">Auto-detect</option>
                    {subcategories.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-2.5 h-4 w-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Description */}
          <div className="card">
            <h2 className="text-base font-semibold text-gray-800 mb-4">3. Description</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Describe your issue <span className="text-red-500">*</span>
                </label>
                <textarea
                  required
                  rows={6}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="input-field resize-y"
                  placeholder="Please describe your issue in detail. Include relevant dates, IDs, and any steps already taken. Minimum 50 characters."
                />
                <div className="flex justify-between items-center mt-1.5">
                  <span
                    className={`text-xs ${
                      description.length < 50 ? 'text-red-500' : 'text-green-600'
                    }`}
                  >
                    {description.length < 50
                      ? `${50 - description.length} more characters needed`
                      : '✓ Minimum length met'}
                  </span>
                  <span className="text-xs text-gray-400">{description.length} chars</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                <div className="flex gap-3">
                  {['English', 'Hinglish', 'Hindi'].map((lang) => (
                    <label
                      key={lang}
                      className={`flex items-center gap-1.5 px-3 py-1.5 border rounded-lg cursor-pointer text-sm transition-all ${
                        language === lang
                          ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                          : 'border-gray-200 hover:border-gray-300 text-gray-600'
                      }`}
                    >
                      <input
                        type="radio"
                        value={lang}
                        checked={language === lang}
                        onChange={() => setLanguage(lang)}
                        className="sr-only"
                      />
                      {lang}
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Section 4: Additional Context */}
          <div className="card">
            <h2 className="text-base font-semibold text-gray-800 mb-1">
              4. Additional Context{' '}
              <span className="text-xs font-normal text-gray-400">(optional)</span>
            </h2>
            <p className="text-xs text-gray-400 mb-4">
              Providing context helps us route your submission faster.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Section</label>
                <input
                  type="text"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                  className="input-field"
                  placeholder="e.g. CS-A"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Hostel Block</label>
                <input
                  type="text"
                  value={hostelBlock}
                  onChange={(e) => setHostelBlock(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Block C"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Course Code</label>
                <input
                  type="text"
                  value={courseCode}
                  onChange={(e) => setCourseCode(e.target.value)}
                  className="input-field"
                  placeholder="e.g. CSE301"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Event Name</label>
                <input
                  type="text"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value)}
                  className="input-field"
                  placeholder="e.g. Annual Fest"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="flex items-start gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={urgentDeadline}
                    onChange={(e) => setUrgentDeadline(e.target.checked)}
                    className="mt-1 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>
                    This issue has an urgent deadline
                    <span className="mt-0.5 block text-xs text-gray-500">
                      The flag raises triage priority but does not determine the final decision.
                    </span>
                  </span>
                </label>
              </div>
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Number</label>
                <input
                  type="tel"
                  value={contactNo}
                  onChange={(e) => setContactNo(e.target.value)}
                  className="input-field"
                  placeholder="e.g. 9876543210"
                />
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              {error}
            </div>
          )}

          {/* Submit */}
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading}
              className="btn-primary px-8 py-3 text-base"
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  <Send className="h-5 w-5" />
                  Submit
                </>
              )}
            </button>
          </div>
        </form>
      ) : (
        <div id="submit-result">
          <SuccessCard result={result} />
          <div className="mt-4 flex justify-center">
            <button onClick={handleNewSubmission} className="btn-secondary">
              + New Submission
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
