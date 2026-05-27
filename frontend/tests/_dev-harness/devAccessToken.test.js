const assert = require('node:assert/strict');

const {
  getAccessTokenPreview,
  normalizeAccessTokenInput,
} = require('../.tmp-dev-token/devAccessToken.js');

assert.equal(normalizeAccessTokenInput(''), null);
assert.equal(normalizeAccessTokenInput('   '), null);
assert.equal(normalizeAccessTokenInput('plain-token'), 'plain-token');
assert.equal(
  normalizeAccessTokenInput('Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'),
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
);
assert.equal(normalizeAccessTokenInput(' bearer   another-token-value   '), 'another-token-value');

assert.equal(getAccessTokenPreview(null), '없음');
assert.equal(getAccessTokenPreview('short-token'), 'short-token');
assert.equal(getAccessTokenPreview('abcdefghijklmnopqrstuvwxyz'), 'abcdefgh...uvwxyz');

console.log('dev access token logic tests passed');
