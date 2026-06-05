// 공통 유틸 함수 export hub

/**
 * ISO 8601 시각을 "방금 전 / N분 전 / N시간 전 / N일 전" 형태의
 * 한국어 상대 시간 문자열로 변환한다. 값이 없으면 빈 문자열.
 */
export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return '';
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}
