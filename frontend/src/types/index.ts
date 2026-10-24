// ─── User & Auth ────────────────────────────────────────────────────────────
export interface User {
  id: number;
  username: string;
  email: string;
  role: 'student' | 'faculty' | 'staff' | 'admin';
  department?: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

// ─── Grievance Submission ────────────────────────────────────────────────────
export interface GrievanceSubmit {
  message_type: 'Grievance' | 'Assistance' | 'Enquiry' | 'Query' | 'Request' | 'Feedback' | 'Positive Feedback';
  description: string;
  selected_master?: string;
  selected_category?: string;
  selected_subcategory?: string;
  language?: string;
  section?: string;
  hostel_block?: string;
  course_code?: string;
  event_name?: string;
  contact_no?: string;
  urgent_deadline?: boolean;
}

// ─── AI Analysis ─────────────────────────────────────────────────────────────
export interface TopClass {
  label: string;
  probability: number;
}

export interface AIAnalysis {
  predicted_master: string;
  predicted_category: string;
  predicted_subcategory: string;
  confidence: number;
  sensitivity_flag: boolean;
  sensitivity_type: string;
  sensitivity_evidence: string[];
  priority_label: string;
  routed_to: string;
  needs_human_review: boolean;
  review_reasons: string[];
  incident_found: boolean;
  incident_id?: string;
  incident_title?: string;
  reply_template?: string;
  baseline_prediction: string;
  model_prediction: string;
  top_classes: TopClass[];
  low_confidence: boolean;
  completeness_issues: string[];
  is_complete: boolean;
  classifier_explanation: string[];
  classifier_available: boolean;
  baseline_keywords: string[];
  baseline_categories: string[];
  priority_score: number;
  priority_reasons: string[];
  routing_basis: string;
  incident_status?: string;
}

// ─── Grievance ────────────────────────────────────────────────────────────────
export interface Grievance {
  grievance_id: string;
  message_type: string;
  description: string;
  status: string;
  created_at: string;
  updated_at?: string;
  ai_analysis?: AIAnalysis;
  human_decision?: HumanDecision;
  status_history?: StatusHistoryEntry[];
  audit_events?: AuditEvent[];
}

export interface AuditEvent {
  action: string;
  actor: string;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface StatusHistoryEntry {
  previous_status?: string | null;
  new_status: string;
  changed_by: string;
  changed_at: string;
}

export interface HumanDecision {
  decided_by: string;
  final_category?: string;
  final_subcategory?: string;
  final_route?: string;
  final_priority?: string;
  decision_notes?: string;
  resolution_solution?: string;
  decided_at: string;
}

export interface SubmitResponse {
  grievance_id: string;
  status: string;
  message: string;
  ai_analysis: AIAnalysis;
  incident?: Record<string, unknown> | null;
}

// ─── Admin ───────────────────────────────────────────────────────────────────
export interface StatsResponse {
  total: number;
  pending_review: number;
  by_priority: Record<string, number>;
  sensitive_count: number;
  by_status: Record<string, number>;
  by_master_category: Record<string, number>;
}

export interface HumanDecisionPayload {
  final_category?: string;
  final_subcategory?: string;
  final_route?: string;
  final_priority?: string;
  decision_notes?: string;
  resolution_solution?: string;
  new_status: 'under_review' | 'resolved' | 'closed' | 'escalated';
}

export interface DraftResponse {
  grievance_id: string;
  draft: string;
  requires_individual_review: boolean;
}

export interface BulkDecisionItem extends HumanDecisionPayload {
  grievance_id: string;
  approved: boolean;
}

// ─── Category Tree ───────────────────────────────────────────────────────────
export interface CategoryTree {
  [master: string]: {
    [category: string]: string[];
  };
}
