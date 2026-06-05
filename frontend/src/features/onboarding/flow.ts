export function shouldUseLocalOnboardingFallback(accessToken: string | null): boolean {
  return !accessToken;
}
