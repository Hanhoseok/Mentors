import { apiClient } from '@/api/client';
import type {
  MentorSelectionPayload,
  OnboardingProfilePayload,
  OnboardingStatusResponse,
} from './types';

export async function getOnboardingStatus(): Promise<OnboardingStatusResponse> {
  const response = await apiClient.get<OnboardingStatusResponse>('/api/onboarding/status');
  return response.data;
}

export async function saveOnboardingProfile(payload: OnboardingProfilePayload): Promise<unknown> {
  const response = await apiClient.post('/api/onboarding/profile', payload);
  return response.data;
}

export async function saveMentorSelection(payload: MentorSelectionPayload): Promise<unknown> {
  const response = await apiClient.post('/api/onboarding/select-mentor', payload);
  return response.data;
}
