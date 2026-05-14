const assert = require('node:assert/strict');

const {
  buildProfilePayload,
  getRecommendedMentors,
  isSurveyComplete,
} = require('../.tmp-onboarding/logic.js');

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

const [firstMentor] = getRecommendedMentors(survey);

assert.equal(
  firstMentor.id,
  'soohyun',
  'a cautious beginner should be matched with the steady mentor first',
);

assert.deepEqual(buildProfilePayload(survey), {
  experience_level: 'beginner',
  interests: ['macro', 'dividend'],
  risk_profile: 'steady',
  learning_goal: 'build-habit',
  preferred_style: 'gentle',
});

console.log('onboarding logic tests passed');
