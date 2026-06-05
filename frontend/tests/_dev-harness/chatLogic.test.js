const assert = require('node:assert/strict');

const {
  buildLearningChatHistoryCards,
  buildLearningChatPreview,
  formatLearningChatDate,
  keepChatScrollPinnedToBottom,
  parseLearningChatEventBuffer,
  shouldSubmitChatOnKeyPress,
} = require('../../.tmp-chat/features/chat/logic.js');
const { resolveSuggestedLearningMentorId } = require('../../.tmp-chat/features/chat/data.js');

const firstChunk = parseLearningChatEventBuffer('event: delta\ndata: {"delta":"안');
assert.equal(firstChunk.events.length, 0, 'partial SSE chunks should wait for more data');

const secondChunk = parseLearningChatEventBuffer(
  `${firstChunk.remainder}녕하세요","done":false}\n\nevent: follow_up_quiz\ndata: {"concept_id":12,"concept_name":"PER","quiz_index":0,"question":"PER은 무엇인가요?","options":["주가 대비 이익","주가 대비 자산"]}\n\n`,
);

assert.deepEqual(
  secondChunk.events.map((event) => event.type),
  ['delta', 'follow_up_quiz'],
  'chat stream parsing should recognize both delta and follow-up quiz events',
);
assert.equal(
  secondChunk.events[0].chunk.delta,
  '안녕하세요',
  'delta payload should preserve streamed Korean text correctly',
);
assert.equal(
  secondChunk.events[1].quiz.concept_name,
  'PER',
  'follow-up quiz payloads should be decoded into quiz events',
);

assert.equal(
  shouldSubmitChatOnKeyPress({ key: 'Enter', shiftKey: false, isComposing: false }),
  true,
  'plain Enter should submit the chat composer on web',
);

assert.equal(
  shouldSubmitChatOnKeyPress({ key: 'Enter', shiftKey: true, isComposing: false }),
  false,
  'Shift+Enter should keep line breaks available in the composer',
);

assert.equal(
  shouldSubmitChatOnKeyPress({ key: 'Enter', shiftKey: false, isComposing: true }),
  false,
  'IME composition should not accidentally submit the composer',
);

assert.equal(
  buildLearningChatPreview([
    {
      id: 1,
      session_id: 1,
      role: 'user',
      content: 'PER이 뭐야?',
      created_at: '2026-05-26T10:00:00Z',
    },
    {
      id: 2,
      session_id: 1,
      role: 'assistant',
      content: 'PER은 주가를 주당순이익으로 나눈 값입니다.',
      created_at: '2026-05-26T10:00:01Z',
    },
  ]),
  'PER은 주가를 주당순이익으로 나눈 값입니다.',
  'history previews should prioritize assistant answers when available',
);

assert.equal(
  formatLearningChatDate('2026-05-26T10:00:00Z'),
  '2026.05.26',
  'chat history dates should render in a compact yyyy.mm.dd format',
);

assert.equal(
  resolveSuggestedLearningMentorId({
    experienceLevel: 'confident',
    interests: ['dividend', 'etf'],
    riskProfile: 'steady',
    learningGoal: 'build-habit',
    preferredStyle: 'gentle',
    selectedMentorId: 3,
    completedAt: '2026-05-26T10:00:00Z',
    syncState: 'remote',
  }),
  3,
  'dividend-heavy learners should start on the dividend mentor even when onboarding mentor ids differ',
);

assert.equal(
  resolveSuggestedLearningMentorId({
    experienceLevel: 'exploring',
    interests: ['ai', 'tech'],
    riskProfile: 'bold',
    learningGoal: 'find-style',
    preferredStyle: 'challenging',
    selectedMentorId: 4,
    completedAt: '2026-05-26T10:00:00Z',
    syncState: 'remote',
  }),
  4,
  'bold growth-oriented learners should default to the momentum mentor when appropriate',
);

const historyCards = buildLearningChatHistoryCards(
  [
    {
      id: 3,
      mentor_id: 2,
      title: null,
      created_at: '2026-05-26T10:00:00Z',
    },
  ],
  {
    3: [
      {
        id: 4,
        session_id: 3,
        role: 'assistant',
        content: '시장 규모와 매출 성장률을 함께 봐야 합니다.',
        created_at: '2026-05-26T10:01:00Z',
      },
    ],
  },
);

assert.equal(historyCards.length, 1, 'history card builders should return one card per session');
assert.equal(historyCards[0].mentor.shortLabel, '성장', 'cards should attach mentor metadata');
assert.equal(historyCards[0].messageCount, 1, 'cards should report message counts from history');

const scrollCalls = [];
assert.equal(
  keepChatScrollPinnedToBottom({
    scrollToEnd(options) {
      scrollCalls.push(options);
    },
  }),
  true,
  'chat helpers should report when they successfully pinned the scroll view to the latest message',
);
assert.deepEqual(
  scrollCalls,
  [{ animated: true }],
  'chat helpers should scroll to the bottom with animation by default',
);
assert.equal(
  keepChatScrollPinnedToBottom(null),
  false,
  'chat helpers should safely no-op when no scroll view is available yet',
);

console.log('chat logic tests passed');
