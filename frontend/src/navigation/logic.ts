export interface MainTabBarMetricsInput {
  bottomInset: number;
  platform: 'android' | 'ios' | 'web';
}

export interface MainTabBarMetrics {
  height: number;
  paddingBottom: number;
  paddingTop: number;
  marginBottom: number;
  marginHorizontal: number;
  borderRadius: number;
}

/**
 * 하단 탭바 지표 — 바닥에서 살짝 띄운 둥근 플로팅 카드.
 * 회색 테두리 대신 부드러운 그림자로 띄움을 표현해, 주변에 회색 박스가 보이지 않게 한다.
 * 탭바는 flex 흐름에 있어 margin 만큼 scene 높이가 줄어들므로, 각 화면 하단 콘텐츠가
 * 카드 위에 정상적으로 자리한다.
 */
export function buildMainTabBarMetrics({
  bottomInset,
}: MainTabBarMetricsInput): MainTabBarMetrics {
  return {
    height: 58,
    paddingBottom: 8,
    paddingTop: 8,
    marginBottom: bottomInset + 8,
    marginHorizontal: 14,
    borderRadius: 24,
  };
}
