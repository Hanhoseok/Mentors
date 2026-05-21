const assert = require('node:assert/strict');

const {
  buildPromotionTestPayload,
  didGrowthProgressAdvance,
  getLearningRecordHintMessage,
  getLearningRecordSegments,
  getGrowthStageCopy,
  getPromotionResultHeadline,
  getUnlockLabel,
  isPromotionTestComplete,
} = require('../.tmp-growth/logic.js');

const eligibleProgress = {
  current_tier: 'T1',
  next_tier: 'T2',
  progress_percent: 80,
  mastered_concepts: 4,
  total_concepts: 5,
  eligible_for_promotion: true,
  promotion_eligible_at: '2026-05-15T09:00:00Z',
  unlocked_features: [],
  next_unlocks: ['debate_arena'],
  promotion_test: {
    target_tier: 'T2',
    passing_score: 80,
    question_count: 2,
    questions: [
      {
        question_id: 't1-q1',
        prompt: 'Question 1',
        choices: [
          { choice_id: 'A', text: 'Choice A' },
          { choice_id: 'B', text: 'Choice B' },
        ],
      },
      {
        question_id: 't1-q2',
        prompt: 'Question 2',
        choices: [
          { choice_id: 'A', text: 'Choice A' },
          { choice_id: 'B', text: 'Choice B' },
        ],
      },
    ],
  },
};

assert.equal(
  isPromotionTestComplete(eligibleProgress.promotion_test.questions, { 't1-q1': 'A' }),
  false,
  'every question should need an answer before submit is enabled',
);

assert.equal(
  isPromotionTestComplete(eligibleProgress.promotion_test.questions, {
    't1-q1': 'A',
    't1-q2': 'B',
  }),
  true,
  'submit should unlock when all question ids have answers',
);

assert.deepEqual(
  buildPromotionTestPayload(eligibleProgress.promotion_test.questions, {
    't1-q2': 'B',
    't1-q1': 'A',
  }),
  {
    answers: [
      { question_id: 't1-q1', choice_id: 'A' },
      { question_id: 't1-q2', choice_id: 'B' },
    ],
  },
  'payload should preserve the server question order',
);

assert.equal(getUnlockLabel('debate_arena'), '멘토 토론 아레나');
assert.equal(getUnlockLabel('extra_mentors'), '추가 멘토 해금');
assert.equal(getUnlockLabel('mystery_feature'), 'mystery feature');

assert.deepEqual(getLearningRecordSegments({ reports: 3, quizzes: 5, arenas: 4 }), [
  { key: 'reports', label: '리포트 3' },
  { key: 'quizzes', label: '퀴즈 5' },
  { key: 'arenas', label: '투기장 4' },
]);

assert.equal(
  didGrowthProgressAdvance(eligibleProgress, {
    ...eligibleProgress,
    progress_percent: 80,
    mastered_concepts: 4,
  }),
  false,
  'unchanged growth snapshots should not stop the sync retry loop early',
);

assert.equal(
  didGrowthProgressAdvance(eligibleProgress, {
    ...eligibleProgress,
    progress_percent: 100,
    mastered_concepts: 5,
    eligible_for_promotion: true,
  }),
  true,
  'a higher mastered concept count should be treated as synced growth progress',
);

assert.equal(getLearningRecordHintMessage('reports'), '이해도 칩을 탭하면 다시 수정할 수 있어요');
assert.equal(
  getLearningRecordHintMessage('quizzes'),
  '문항을 탭하면 풀이와 결과를 다시 볼 수 있어요',
);

assert.deepEqual(getGrowthStageCopy(eligibleProgress), {
  badge: '승급 가능',
  title: 'T2 승급시험에 도전할 수 있어요',
  description: '현재 티어 이해도 80%를 달성했어요. 지금 바로 시험을 시작할 수 있어요.',
});

assert.deepEqual(
  getGrowthStageCopy({
    ...eligibleProgress,
    progress_percent: 40,
    mastered_concepts: 2,
    eligible_for_promotion: false,
    promotion_test: null,
  }),
  {
    badge: '성장 진행 중',
    title: '현재 T1 이해도를 쌓는 중이에요',
    description: '개념 2/5개를 완료했어요. 승급시험까지 40% 더 채우면 됩니다.',
  },
);

assert.equal(
  getPromotionResultHeadline({
    previous_tier: 'T1',
    current_tier: 'T2',
    target_tier: 'T2',
    passed: true,
    score_percent: 80,
    correct_answers: 4,
    total_questions: 5,
    unlocked_features: ['debate_arena'],
    message: 'Promotion test passed.',
  }),
  'T2로 승급했어요',
);

assert.equal(
  getPromotionResultHeadline({
    previous_tier: 'T2',
    current_tier: 'T2',
    target_tier: 'T3',
    passed: false,
    score_percent: 60,
    correct_answers: 3,
    total_questions: 5,
    unlocked_features: ['debate_arena'],
    message: 'Promotion test not passed. You can retry immediately.',
  }),
  '이번에는 T2 유지예요',
);

console.log('growth logic tests passed');
