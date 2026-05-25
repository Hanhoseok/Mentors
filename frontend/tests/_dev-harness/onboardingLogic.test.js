const assert = require('node:assert/strict');

const {
  buildCompletedStatusFromSurvey,
  buildRecommendedMentorsFromApi,
  buildProfilePayload,
  getOnboardingProgressValue,
  getOnboardingStepLabel,
  getRecommendedMentors,
  isSurveyComplete,
} = require('../../.tmp-harness-onboarding/_dev-harness/onboarding/logic.js');
const {
  onboardingInterestOptions,
  interestOptions,
  profileInterestOptions,
  getInterestLabel,
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
  'Warren Buffett',
  'frontend fallback mentor data should be aligned to the real investor catalog',
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
      name: 'Warren Buffett',
    },
    completed_at: '2026-05-25T10:55:00.000Z',
  },
  'completed onboarding should be convertible into a populated status snapshot for immediate UI hydration',
);

assert.deepEqual(
  buildRecommendedMentorsFromApi([
    {
      id: 2,
      slug: 'peter-lynch',
      name: 'Peter Lynch',
      title: 'Everyday Stock Picking Mentor',
      summary: 'Company-first research with practical examples and accessible explanations.',
      reason: 'Peter Lynch is recommended because it supports the goal to understand-news.',
    },
  ])[0],
  {
    id: 2,
    slug: 'peter-lynch',
    name: 'Peter Lynch',
    title: 'Everyday Stock Picking Mentor',
    oneLiner: 'Company-first research with practical examples and accessible explanations.',
    philosophy: '생활 속에서 이해한 기업을 꾸준히 관찰하면 좋은 아이디어는 가까이에 있다고 봅니다.',
    idealFor: '뉴스와 기업 사례를 연결해서 개별 종목 감각을 키우고 싶은 사용자',
    accentColor: '#C66B5A',
    focusTags: [
      'value',
      'tech',
      'it',
      'bio',
      'global',
      'dividend',
      'domestic-stock',
      'us-stock',
      'semiconductor',
      'battery',
      'ai',
      'entertainment-media',
      'fashion-consumer',
    ],
    experienceMatch: ['beginner', 'exploring', 'confident'],
    riskMatch: ['balanced', 'bold'],
    styleMatch: ['gentle', 'challenging'],
    goalMatch: ['find-style', 'understand-news'],
    strengths: ['생활밀착형 기업 분석', '쉬운 사례 중심 설명', '성장주 감각 키우기'],
    score: 1,
    reasons: ['Peter Lynch is recommended because it supports the goal to understand-news.'],
  },
  'API recommendation should be decorated with frontend presentation fields',
);

console.log('onboarding logic tests passed');
