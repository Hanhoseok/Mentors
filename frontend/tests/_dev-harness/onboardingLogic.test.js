const assert = require('node:assert/strict');

const {
  buildCompletedStatusFromSurvey,
  buildProfilePayload,
  buildRecommendedMentorsFromApi,
  getOnboardingProgressValue,
  getOnboardingStepLabel,
  getRecommendedMentors,
  isSurveyComplete,
  shouldUseLocalOnboardingFallback,
} = require('../../.tmp-harness-onboarding/_dev-harness/onboarding/logic.js');
const {
  getInterestLabel,
  onboardingInterestOptions,
  profileInterestOptions,
} = require('../../.tmp-harness-onboarding/_dev-harness/onboarding/data.js');

const survey = {
  experienceLevel: 'beginner',
  interests: ['macro', 'dividend'],
  riskProfile: 'steady',
  learningGoal: 'build-habit',
  preferredStyle: 'gentle',
};

assert.equal(
  isSurveyComplete({
    ...survey,
    interests: [],
  }),
  false,
  'interest selection should be required',
);

assert.equal(isSurveyComplete(survey), true, 'survey with all answers should be complete');

assert.equal(getOnboardingStepLabel(0), '1 / 6');
assert.equal(getOnboardingStepLabel(5), '6 / 6');
assert.equal(getOnboardingProgressValue(2), 0.5);
assert.equal(
  shouldUseLocalOnboardingFallback(null),
  true,
  'anonymous onboarding can fall back to local completion when no backend identity exists',
);
assert.equal(
  shouldUseLocalOnboardingFallback('jwt-token'),
  false,
  'authenticated onboarding should not silently fall back to local completion when backend sync fails',
);

assert.equal(
  onboardingInterestOptions.some((option) => option.value === 'it'),
  true,
  'interest choices should include IT/platform sectors for stock-focused learners',
);

assert.equal(
  onboardingInterestOptions.some((option) => option.value === 'bio'),
  true,
  'interest choices should include bio/healthcare sectors for stock-focused learners',
);

assert.deepEqual(
  onboardingInterestOptions.map((option) => option.value),
  profileInterestOptions.map((option) => option.value),
  'onboarding and settings should show the same interest option set',
);

assert.equal(
  profileInterestOptions.some((option) => option.value === 'domestic-stock'),
  true,
  'profile interest settings should expose the Figma-style domestic stock chip',
);

assert.equal(
  getInterestLabel('semiconductor'),
  '반도체',
  'new profile-only interest tags should still resolve to a readable label in summaries',
);

const [firstMentor] = getRecommendedMentors(survey);

assert.equal(firstMentor.id, 1, 'a cautious beginner should be matched with mentor id 1 first');
assert.equal(
  firstMentor.name,
  '워런 버핏',
  'frontend fallback mentor data should be aligned to the localized investor catalog',
);

assert.deepEqual(buildProfilePayload(survey), {
  experience_level: 'beginner',
  interests: ['macro', 'dividend'],
  risk_profile: 'steady',
  learning_goal: 'build-habit',
  preferred_style: 'gentle',
  answers: [
    {
      question_code: 'experience_level',
      question_text: '현재 투자 경험',
      answer_value: 'beginner',
    },
    {
      question_code: 'interests',
      question_text: '관심 있는 주제',
      answer_value: 'macro, dividend',
    },
    {
      question_code: 'risk_profile',
      question_text: '리스크 성향',
      answer_value: 'steady',
    },
    {
      question_code: 'learning_goal',
      question_text: '이번 온보딩의 목표',
      answer_value: 'build-habit',
    },
    {
      question_code: 'preferred_style',
      question_text: '원하는 코칭 스타일',
      answer_value: 'gentle',
    },
  ],
});

assert.deepEqual(
  buildCompletedStatusFromSurvey(survey, 1, '2026-05-25T10:55:00.000Z'),
  {
    onboarded: true,
    tier: 'T1',
    profile: {
      experience_level: 'beginner',
      interests: ['macro', 'dividend'],
      risk_profile: 'steady',
      learning_goal: 'build-habit',
      preferred_style: 'gentle',
    },
    selected_mentor: {
      id: 1,
      slug: 'warren-buffett',
      name: '워런 버핏',
    },
    completed_at: '2026-05-25T10:55:00.000Z',
  },
  'completed onboarding should be convertible into a populated status snapshot for immediate UI hydration',
);

const [decoratedRecommendation] = buildRecommendedMentorsFromApi([
  {
    id: 2,
    slug: 'peter-lynch',
    name: '피터 린치',
    title: '생활밀착형 종목 발굴 멘토',
    summary: '생활 속 기업 사례를 바탕으로 종목을 보는 관점을 잡아줘요.',
    reason: '뉴스와 기업 이슈를 종목 아이디어로 연결하고 싶은 학습 목표에 잘 맞아요.',
  },
]);

assert.equal(decoratedRecommendation.id, 2);
assert.equal(decoratedRecommendation.name, '피터 린치');
assert.equal(decoratedRecommendation.title, '생활밀착형 종목 발굴 멘토');
assert.equal(
  decoratedRecommendation.oneLiner,
  '생활 속 기업 사례를 바탕으로 종목을 보는 관점을 잡아줘요.',
);
assert.equal(decoratedRecommendation.score, 1);
assert.deepEqual(decoratedRecommendation.reasons, [
  '뉴스와 기업 이슈를 종목 아이디어로 연결하고 싶은 학습 목표에 잘 맞아요.',
]);
assert.equal(
  decoratedRecommendation.focusTags.includes('it'),
  true,
  'decorated recommendations should keep the frontend mentor focus tags',
);
assert.equal(
  decoratedRecommendation.strengths.length > 0,
  true,
  'decorated recommendations should preserve mentor presentation strengths',
);

console.log('onboarding logic tests passed');
