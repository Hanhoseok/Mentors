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
  MentorProfile,
  MentorRecommendation,
  OnboardingProfilePayload,
  OnboardingSurvey,
  OnboardingSyncState,
} from './types';

type CompletedSurvey = Omit<
  CompletedOnboardingProfile,
  'completedAt' | 'selectedMentorId' | 'syncState'
>;

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

export function getMentorById(id: string): MentorProfile | null {
  return mentorCatalog.find((mentor) => mentor.id === id) ?? null;
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
  };
}

export function buildCompletedProfile(
  survey: OnboardingSurvey,
  mentorId: string,
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
