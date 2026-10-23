import apiClient from './client.ts';
import type {
  GrievanceSubmit,
  SubmitResponse,
  Grievance,
  StatsResponse,
  HumanDecisionPayload,
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
