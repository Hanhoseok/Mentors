import type {
  InterestTag,
  OnboardingProfilePayload,
  OnboardingStatusResponse,
  PreferredStyle,
} from '@/features/onboarding/types';

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

/**
 * 사용자가 직접 입력한 시간 문자열을 HH:MM로 정규화한다.
 * 콜론 유무 모두 허용한다: "9", "09", "900", "0900", "1830", "9:00", "09:00", "18:30".
 * 유효하지 않으면 null.
 */
export function normalizeReminderTimeInput(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  let hour: number;
  let minute: number;

  const colon = /^(\d{1,2}):(\d{1,2})$/.exec(trimmed);
  if (colon) {
    hour = Number(colon[1]);
    minute = Number(colon[2]);
  } else {
    // 콜론이 없으면 숫자만 허용 (그 외 문자가 섞이면 거부)
    if (!/^\d+$/.test(trimmed)) return null;
    if (trimmed.length <= 2) {
      hour = Number(trimmed); // "9" / "09" → 정시
      minute = 0;
    } else if (trimmed.length === 3) {
      hour = Number(trimmed.slice(0, 1)); // "930" → 9:30
      minute = Number(trimmed.slice(1));
    } else if (trimmed.length === 4) {
      hour = Number(trimmed.slice(0, 2)); // "0930" / "1830"
      minute = Number(trimmed.slice(2));
    } else {
      return null;
    }
  }

  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
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
