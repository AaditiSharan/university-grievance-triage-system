import apiClient from './client.ts';
import type { LoginResponse, User } from '../types';

/**
 * Authenticate a user and receive an access token.
 * The backend expects form-encoded data for OAuth2 password flow.
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const params = new URLSearchParams();
  params.append('username', username);
  params.append('password', password);

  const response = await apiClient.post<LoginResponse>('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return response.data;
}

/**
 * Register a new user account.
 */
export async function register(
  username: string,
  email: string,
  password: string,
  role: 'student' | 'faculty' | 'staff'
): Promise<User> {
  const response = await apiClient.post<User>('/auth/register', {
    username,
    email,
    password,
    role,
  });
  return response.data;
}

/**
 * Fetch the currently authenticated user's profile.
 */
export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/auth/me');
  return response.data;
}
