import { create } from 'zustand';
import type { CompletedOnboardingProfile } from '@/features/onboarding/types';

type OnboardingSource = 'local' | 'remote';

interface UserState {
  accessToken: string | null;
  hasCompletedOnboarding: boolean;
  onboardingSource: OnboardingSource | null;
  onboardingProfile: CompletedOnboardingProfile | null;
  setAccessToken: (token: string) => void;
  clearToken: () => void;
  finishOnboarding: (input: {
    profile: CompletedOnboardingProfile | null;
    source: OnboardingSource;
  }) => void;
  resetOnboarding: () => void;
}

export const useUserStore = create<UserState>((set) => ({
  accessToken: null,
  hasCompletedOnboarding: false,
  onboardingSource: null,
  onboardingProfile: null,
  setAccessToken: (token) => set({ accessToken: token }),
  clearToken: () => set({ accessToken: null }),
  finishOnboarding: ({ profile, source }) =>
    set({
      hasCompletedOnboarding: true,
      onboardingProfile: profile,
      onboardingSource: source,
    }),
  resetOnboarding: () =>
    set({
      hasCompletedOnboarding: false,
      onboardingProfile: null,
      onboardingSource: null,
    }),
}));
