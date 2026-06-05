import {
  getExperienceLevelLabel,
  getInterestLabel,
  getLearningGoalLabel,
  getPreferredStyleLabel,
  getRiskProfileLabel,
  mentorCatalog,
} from './data';
import type {
  CompletedOnboardingProfile,
  InterestTag,
  MentorSummaryResponse,
  MentorProfile,
  MentorRecommendation,
  OnboardingProfilePayload,
  OnboardingStatusResponse,
  OnboardingSurvey,
  OnboardingSyncState,
} from '../../features/onboarding/types';
export { shouldUseLocalOnboardingFallback } from '../../features/onboarding/flow';

type CompletedSurvey = Omit<
  CompletedOnboardingProfile,
  'completedAt' | 'selectedMentorId' | 'syncState'
>;

export const ONBOARDING_STEP_COUNT = 6;

export const EMPTY_ONBOARDING_SURVEY: OnboardingSurvey = {
  experienceLevel: null,
  interests: [],
  riskProfile: null,
  learningGoal: null,
  preferredStyle: null,
};

export function toggleInterest(interests: InterestTag[], interest: InterestTag): InterestTag[] {
  if (interests.includes(interest)) {
    return interests.filter((item) => item !== interest);
  }

  return [...interests, interest];
}

export function getOnboardingStepLabel(
  stepIndex: number,
  totalSteps = ONBOARDING_STEP_COUNT,
): string {
  if (totalSteps <= 0) {
    return '0 / 0';
  }

  const currentStep = Math.min(totalSteps, Math.max(1, stepIndex + 1));
  return `${currentStep} / ${totalSteps}`;
}

export function getOnboardingProgressValue(
  stepIndex: number,
  totalSteps = ONBOARDING_STEP_COUNT,
): number {
  if (totalSteps <= 0) {
    return 0;
  }

  const currentStep = Math.min(totalSteps, Math.max(1, stepIndex + 1));
  return currentStep / totalSteps;
}

export function isSurveyComplete(survey: OnboardingSurvey): survey is CompletedSurvey {
  return Boolean(
    survey.experienceLevel &&
    survey.interests.length > 0 &&
    survey.riskProfile &&
    survey.learningGoal &&
    survey.preferredStyle,
  );
}

function getMentorScore(survey: OnboardingSurvey, mentor: MentorProfile): number {
  let score = 0;

  if (survey.experienceLevel && mentor.experienceMatch.includes(survey.experienceLevel)) {
    score += 3;
  }

  if (survey.riskProfile && mentor.riskMatch.includes(survey.riskProfile)) {
    score += 3;
  }

  if (survey.learningGoal && mentor.goalMatch.includes(survey.learningGoal)) {
    score += 2;
  }

  if (survey.preferredStyle && mentor.styleMatch.includes(survey.preferredStyle)) {
    score += 2;
  }

  for (const interest of survey.interests) {
    if (mentor.focusTags.includes(interest)) {
      score += 2;
    }
  }

  return score;
}

function buildRecommendationReasons(survey: OnboardingSurvey, mentor: MentorProfile): string[] {
  const reasons: string[] = [];

  if (survey.riskProfile && mentor.riskMatch.includes(survey.riskProfile)) {
    reasons.push(`${getRiskProfileLabel(survey.riskProfile)} 성향과 잘 맞는 멘토예요.`);
  }

  if (survey.learningGoal && mentor.goalMatch.includes(survey.learningGoal)) {
    reasons.push(`${getLearningGoalLabel(survey.learningGoal)} 목표에 맞춰 대화를 설계해요.`);
  }

  if (survey.preferredStyle && mentor.styleMatch.includes(survey.preferredStyle)) {
    reasons.push(
      `${getPreferredStyleLabel(survey.preferredStyle)} 설명 방식을 선호하는 경우 특히 잘 맞아요.`,
    );
  }

  const matchedInterests = survey.interests.filter((interest) =>
    mentor.focusTags.includes(interest),
  );
  if (matchedInterests.length > 0) {
    reasons.push(
      `${matchedInterests.map(getInterestLabel).join(', ')} 관심사를 깊게 이어가기 좋아요.`,
    );
  }

  if (survey.experienceLevel && mentor.experienceMatch.includes(survey.experienceLevel)) {
    reasons.push(`${getExperienceLevelLabel(survey.experienceLevel)} 단계에 맞는 난도로 대화해요.`);
  }

  return reasons.slice(0, 3);
}

export function getRecommendedMentors(survey: OnboardingSurvey): MentorRecommendation[] {
  return mentorCatalog
    .map((mentor) => ({
      ...mentor,
      score: getMentorScore(survey, mentor),
      reasons: buildRecommendationReasons(survey, mentor),
    }))
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }

      return left.name.localeCompare(right.name, 'ko-KR');
    });
}

export function getMentorById(id: number): MentorProfile | null {
  return mentorCatalog.find((mentor) => mentor.id === id) ?? null;
}

export function buildRecommendedMentorsFromApi(
  recommendedMentors: MentorSummaryResponse[],
): MentorRecommendation[] {
  return recommendedMentors.map((mentor, index) => {
    const catalogMentor = getMentorById(mentor.id);

    if (!catalogMentor) {
      return {
        id: mentor.id,
        slug: mentor.slug,
        name: mentor.name,
        title: mentor.title,
        oneLiner: mentor.summary,
        philosophy: mentor.summary,
        idealFor: mentor.reason,
        accentColor: '#355CDE',
        focusTags: [],
        experienceMatch: [],
        riskMatch: [],
        styleMatch: [],
        goalMatch: [],
        strengths: [],
        score: recommendedMentors.length - index,
        reasons: [mentor.reason],
      };
    }

    return {
      ...catalogMentor,
      title: mentor.title,
      oneLiner: mentor.summary,
      score: recommendedMentors.length - index,
      reasons: [mentor.reason],
    };
  });
}

function buildSurveyAnswers(survey: CompletedSurvey): OnboardingProfilePayload['answers'] {
  return [
    {
      question_code: 'experience_level',
      question_text: '현재 투자 경험',
      answer_value: survey.experienceLevel,
    },
    {
      question_code: 'interests',
      question_text: '관심 있는 주제',
      answer_value: survey.interests.join(', '),
    },
    {
      question_code: 'risk_profile',
      question_text: '리스크 성향',
      answer_value: survey.riskProfile,
    },
    {
      question_code: 'learning_goal',
      question_text: '이번 온보딩의 목표',
      answer_value: survey.learningGoal,
    },
    {
      question_code: 'preferred_style',
      question_text: '원하는 코칭 스타일',
      answer_value: survey.preferredStyle,
    },
  ];
}

export function buildProfilePayload(survey: OnboardingSurvey): OnboardingProfilePayload {
  if (!isSurveyComplete(survey)) {
    throw new Error('Survey is incomplete');
  }

  return {
    experience_level: survey.experienceLevel,
    interests: survey.interests,
    risk_profile: survey.riskProfile,
    learning_goal: survey.learningGoal,
    preferred_style: survey.preferredStyle,
    answers: buildSurveyAnswers(survey),
  };
}

export function buildCompletedProfile(
  survey: OnboardingSurvey,
  mentorId: number,
  syncState: OnboardingSyncState,
): CompletedOnboardingProfile {
  if (!isSurveyComplete(survey)) {
    throw new Error('Survey is incomplete');
  }

  return {
    ...survey,
    selectedMentorId: mentorId,
    completedAt: new Date().toISOString(),
    syncState,
  };
}

export function buildCompletedStatusFromSurvey(
  survey: OnboardingSurvey,
  mentorId: number,
  completedAt = new Date().toISOString(),
): OnboardingStatusResponse {
  if (!isSurveyComplete(survey)) {
    throw new Error('Survey is incomplete');
  }

  const mentor = getMentorById(mentorId);
  if (!mentor) {
    throw new Error('Unknown mentor');
  }

  return {
    onboarded: true,
    tier: 'T1',
    profile: {
      experience_level: survey.experienceLevel,
      interests: survey.interests,
      risk_profile: survey.riskProfile,
      learning_goal: survey.learningGoal,
      preferred_style: survey.preferredStyle,
    },
    selected_mentor: {
      id: mentor.id,
      slug: mentor.slug,
      name: mentor.name,
    },
    completed_at: completedAt,
  };
}

export function buildCompletedProfileFromStatus(
  status: OnboardingStatusResponse,
): CompletedOnboardingProfile | null {
  if (!status.profile || !status.selected_mentor || !status.completed_at) {
    return null;
  }

  return {
    experienceLevel: status.profile.experience_level,
    interests: status.profile.interests,
    riskProfile: status.profile.risk_profile,
    learningGoal: status.profile.learning_goal,
    preferredStyle: status.profile.preferred_style,
    selectedMentorId: status.selected_mentor.id,
    completedAt: status.completed_at,
    syncState: 'remote',
  };
}
