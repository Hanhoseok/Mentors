import { apiClient } from '@/api/client';
import type {
  OnboardingProfileResponse,
  MentorSelectionPayload,
  OnboardingProfilePayload,
  OnboardingStatusResponse,
} from './types';

export async function getOnboardingStatus(): Promise<OnboardingStatusResponse> {
  const response = await apiClient.get<OnboardingStatusResponse>('/api/onboarding/status');
  return response.data;
}

export async function saveOnboardingProfile(
  payload: OnboardingProfilePayload,
): Promise<OnboardingProfileResponse> {
  const response = await apiClient.post<OnboardingProfileResponse>(
    '/api/onboarding/profile',
    payload,
  );
  return response.data;
}

export async function saveMentorSelection(
  payload: MentorSelectionPayload,
): Promise<OnboardingStatusResponse> {
  const response = await apiClient.post<OnboardingStatusResponse>(
    '/api/onboarding/select-mentor',
    payload,
  );
  return response.data;
}

export async function resetOnboardingProfile(): Promise<OnboardingStatusResponse> {
  const response = await apiClient.post<OnboardingStatusResponse>('/api/onboarding/reset');
  return response.data;
}
