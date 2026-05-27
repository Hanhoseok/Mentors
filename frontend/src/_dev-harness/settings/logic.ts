import type {
  InterestTag,
  OnboardingProfilePayload,
  OnboardingStatusResponse,
  PreferredStyle,
} from '../../features/onboarding/types';

interface LearningPreferenceOverrides {
  interests: InterestTag[];
  preferredStyle: PreferredStyle;
}

interface ReminderPreferenceInput {
  learningReminderEnabled: boolean;
  dailyReportReminderEnabled: boolean;
  reminderTime: string;
}

export interface ScheduledReminderRequest {
  key: 'learning-reminder' | 'daily-report';
  title: string;
  body: string;
  trigger: {
    hour: number;
    minute: number;
  };
}

function buildInterestKey(interests: InterestTag[]): string {
  return [...new Set(interests)].sort().join('|');
}

export function buildLearningPreferenceSeed(input: {
  interests: InterestTag[];
  preferredStyle: PreferredStyle;
}): string {
  return `${buildInterestKey(input.interests)}::${input.preferredStyle}`;
}

export function hasLearningPreferenceChanges(
  profile:
    | NonNullable<OnboardingStatusResponse['profile']>
    | {
        interests: InterestTag[];
        preferred_style: PreferredStyle;
      },
  overrides: LearningPreferenceOverrides,
): boolean {
  return (
    buildInterestKey(profile.interests) !== buildInterestKey(overrides.interests) ||
    profile.preferred_style !== overrides.preferredStyle
  );
}

function parseReminderTime(value: string): { hour: number; minute: number } {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) {
    throw new Error('Invalid reminder time');
  }

  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    throw new Error('Invalid reminder time');
  }

  return { hour, minute };
}

export function formatReminderTime(value: string): string {
  const { hour, minute } = parseReminderTime(value);
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function shiftReminderTime(value: string, minuteDelta: number): string {
  const { hour, minute } = parseReminderTime(value);
  const baseMinutes = hour * 60 + minute;
  const totalMinutes = (((baseMinutes + minuteDelta) % 1440) + 1440) % 1440;
  const nextHour = Math.floor(totalMinutes / 60);
  const nextMinute = totalMinutes % 60;
  return `${String(nextHour).padStart(2, '0')}:${String(nextMinute).padStart(2, '0')}`;
}

export function buildLearningPreferencesPayload(
  profile:
    | NonNullable<OnboardingStatusResponse['profile']>
    | {
        experience_level: OnboardingProfilePayload['experience_level'];
        interests: OnboardingProfilePayload['interests'];
        risk_profile: OnboardingProfilePayload['risk_profile'];
        learning_goal: OnboardingProfilePayload['learning_goal'];
        preferred_style: OnboardingProfilePayload['preferred_style'];
      },
  overrides: LearningPreferenceOverrides,
): OnboardingProfilePayload {
  return {
    experience_level: profile.experience_level,
    interests: overrides.interests,
    risk_profile: profile.risk_profile,
    learning_goal: profile.learning_goal,
    preferred_style: overrides.preferredStyle,
    answers: [],
  };
}

export function buildScheduledReminderRequests(
  input: ReminderPreferenceInput,
): ScheduledReminderRequest[] {
  const trigger = parseReminderTime(input.reminderTime);
  const requests: ScheduledReminderRequest[] = [];

  if (input.learningReminderEnabled) {
    requests.push({
      key: 'learning-reminder',
      title: '오늘의 경제 학습을 이어가볼까요?',
      body: '멘토와 함께 개념과 시장 흐름을 차근차근 정리해보세요.',
      trigger,
    });
  }

  if (input.dailyReportReminderEnabled) {
    requests.push({
      key: 'daily-report',
      title: '데일리 리포트가 준비됐어요',
      body: '오늘의 시장 흐름과 핵심 이슈를 가볍게 훑어보세요.',
      trigger,
    });
  }

  return requests;
}
