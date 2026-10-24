import apiClient from './client.ts';
import type {
  GrievanceSubmit,
  SubmitResponse,
  Grievance,
  StatsResponse,
  HumanDecisionPayload,
  DraftResponse,
  BulkDecisionItem,
} from '../types';

/** Submit a new grievance / query / request / feedback. */
export async function submitGrievance(data: GrievanceSubmit): Promise<SubmitResponse> {
  const response = await apiClient.post<SubmitResponse>('/rms/submit', data);
  return response.data;
}

/** Track a grievance owned by the signed-in user (or accessible to an admin). */
export async function trackGrievance(grievance_id: string): Promise<Grievance> {
  const response = await apiClient.get<Grievance>(`/rms/track/${encodeURIComponent(grievance_id)}`);
  return response.data;
}

/** Fetch all grievances submitted by the current user. */
export async function getMyGrievances(): Promise<Grievance[]> {
  const response = await apiClient.get<Grievance[]>('/rms/my-grievances');
  return response.data;
}

/** Admin: get all grievances (unfiltered). */
export async function getAdminGrievances(): Promise<Grievance[]> {
  const response = await apiClient.get<Grievance[]>('/rms/admin/grievances');
  return response.data;
}

/** Admin: submit a human review decision for a grievance. */
export async function submitHumanDecision(
  grievance_id: string,
  payload: HumanDecisionPayload
): Promise<Grievance> {
  const response = await apiClient.post<Grievance>(
    `/rms/admin/review/${encodeURIComponent(grievance_id)}`,
    payload
  );
  return response.data;
}

/** Admin: fetch aggregate statistics. */
export async function getAdminStats(): Promise<StatsResponse> {
  const response = await apiClient.get<StatsResponse>('/rms/admin/stats');
  return response.data;
}

/** Faculty may read their department queue; staff and admins may also manage it. */
export async function getStaffGrievances(): Promise<Grievance[]> {
  const response = await apiClient.get<Grievance[]>('/rms/staff/grievances');
  return response.data;
}

export async function getStaffStats(): Promise<Pick<StatsResponse, 'total' | 'by_status' | 'pending_review' | 'sensitive_count'>> {
  const response = await apiClient.get('/rms/staff/stats');
  return response.data;
}

export async function submitStaffDecision(
  grievance_id: string,
  payload: HumanDecisionPayload
): Promise<Grievance> {
  const response = await apiClient.post<Grievance>(
    `/rms/staff/review/${encodeURIComponent(grievance_id)}`,
    payload
  );
  return response.data;
}

export async function requestResolutionDrafts(grievance_ids: string[]): Promise<DraftResponse[]> {
  const response = await apiClient.post<{ drafts: DraftResponse[]; saved_or_sent: boolean }>(
    '/rms/staff/draft-resolutions',
    { grievance_ids }
  );
  return response.data.drafts;
}

export async function submitBulkStaffDecisions(items: BulkDecisionItem[]): Promise<Grievance[]> {
  const response = await apiClient.post<{ updated: Grievance[]; count: number }>(
    '/rms/staff/bulk-review',
    { items }
  );
  return response.data.updated;
}
