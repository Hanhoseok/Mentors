export interface MainTabBarMetricsInput {
  bottomInset: number;
  platform: 'android' | 'ios' | 'web';
}

export interface MainTabBarMetrics {
  height: number;
  paddingBottom: number;
  paddingTop: number;
}

export function buildMainTabBarMetrics({
  bottomInset,
  platform,
}: MainTabBarMetricsInput): MainTabBarMetrics {
  const paddingBottom = platform === 'ios' ? Math.max(bottomInset, 20) : Math.max(bottomInset, 12);
  const height = (platform === 'ios' ? 60 : 58) + paddingBottom;

  return {
    height,
    paddingBottom,
    paddingTop: 10,
  };
}
