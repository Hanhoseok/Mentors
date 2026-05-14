export type ExperienceLevel = 'beginner' | 'exploring' | 'confident';
export type InterestTag = 'macro' | 'dividend' | 'value' | 'tech' | 'etf' | 'global';
export type RiskProfile = 'steady' | 'balanced' | 'bold';
export type LearningGoal = 'build-habit' | 'understand-news' | 'find-style';
export type PreferredStyle = 'gentle' | 'structured' | 'challenging';
export type OnboardingSyncState = 'local' | 'remote';

export interface SelectOption<T extends string> {
  value: T;
  label: string;
  description: string;
}

export interface OnboardingSurvey {
  experienceLevel: ExperienceLevel | null;
  interests: InterestTag[];
  riskProfile: RiskProfile | null;
  learningGoal: LearningGoal | null;
  preferredStyle: PreferredStyle | null;
}

export interface CompletedOnboardingProfile {
  experienceLevel: ExperienceLevel;
  interests: InterestTag[];
  riskProfile: RiskProfile;
  learningGoal: LearningGoal;
  preferredStyle: PreferredStyle;
  selectedMentorId: string;
  completedAt: string;
  syncState: OnboardingSyncState;
}

export interface MentorProfile {
  id: string;
  name: string;
  title: string;
  oneLiner: string;
  philosophy: string;
  idealFor: string;
  accentColor: string;
  focusTags: InterestTag[];
  experienceMatch: ExperienceLevel[];
  riskMatch: RiskProfile[];
  styleMatch: PreferredStyle[];
  goalMatch: LearningGoal[];
  strengths: string[];
}

export interface MentorRecommendation extends MentorProfile {
  score: number;
  reasons: string[];
}

export interface OnboardingProfilePayload {
  experience_level: ExperienceLevel;
  interests: InterestTag[];
  risk_profile: RiskProfile;
  learning_goal: LearningGoal;
  preferred_style: PreferredStyle;
}

export interface MentorSelectionPayload {
  mentor_id: string;
}

export interface OnboardingStatusResponse {
  user_id?: string;
  onboarded: boolean;
}
