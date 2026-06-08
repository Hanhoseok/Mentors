const assert = require('node:assert/strict');

const {
  getHeaderActionIconName,
  getIndustryIconName,
  getNotificationTypeIconName,
  getTabIconName,
} = require('../../.tmp-icons/ui/iconTokens.js');

assert.equal(
  getTabIconName('Search'),
  'compass',
  'search tab should use a softer exploration icon instead of a raw magnifier emoji',
);

assert.equal(
  getTabIconName('MentorChat'),
  'message-text',
  'mentor chat tab should keep the talk bubble meaning with a rounded filled icon',
);

assert.equal(
  getTabIconName('DebateArena'),
  'sword-cross',
  'debate tab should preserve the duel metaphor with a native icon',
);

assert.equal(
  getHeaderActionIconName('notifications'),
  'bell-badge',
  'notification actions should use the richer bell icon variant',
);

assert.equal(
  getHeaderActionIconName('scrap'),
  'bookmark',
  'scrap actions should use a bookmark instead of pin/bookmark emoji text',
);

assert.equal(
  getNotificationTypeIconName('daily_report'),
  'chart-box',
  'daily report notifications should use a chart-shaped icon token',
);

assert.equal(
  getIndustryIconName('화학'),
  'flask',
  'industry cards should expose icon tokens instead of emoji glyphs',
);

assert.equal(
  getIndustryIconName('없는 산업'),
  'bookmark',
  'unknown industries should fall back to the generic bookmark token',
);

console.log('icon token tests passed');
