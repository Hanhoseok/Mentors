export function normalizeAccessTokenInput(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) {
    return null;
  }

  const withoutBearer = trimmed.replace(/^bearer\s+/i, '').trim();
  return withoutBearer || null;
}

export function getAccessTokenPreview(token: string | null): string {
  if (!token) {
    return '없음';
  }

  if (token.length <= 16) {
    return token;
  }

  return `${token.slice(0, 8)}...${token.slice(-6)}`;
}
