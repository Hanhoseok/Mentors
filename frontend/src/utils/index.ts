// 공통 유틸 함수 export hub

import { Linking, Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import { colors } from '@/constants/colors';

/**
 * AI 요약문 등에서 노출된 링크/URL을 제거한다.
 * 한글 본문의 부등호(<, >)는 건드리지 않으며, URL과 마크다운 링크만 정리한다.
 */
export function stripUrlsFromText(text: string | null | undefined): string | null {
  if (!text) return null;
  let s = text;
  // HTML 태그 제거 — '<' 뒤가 글자/슬래시/!일 때만(실제 태그). '수익률 <10%' 같은
  // 한글 부등호는 보존(이전 회귀 방지). RSS content의 <a href> 링크 등을 정리한다.
  s = s.replace(/<\/?[a-zA-Z!][^>]*>/g, ' ');
  // 흔한 HTML 엔티티 디코드
  s = s
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#3?9;/gi, "'");
  // 마크다운 링크 [라벨](url) → 라벨만 유지
  s = s.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  // 원시 URL 제거 (http/https, www)
  s = s.replace(/\bhttps?:\/\/[^\s)\]]+/gi, '');
  s = s.replace(/\bwww\.[^\s)\]]+/gi, '');
  // 빈 괄호/대괄호 정리
  s = s.replace(/\(\s*\)/g, '').replace(/\[\s*\]/g, '');
  // "출처:" 등 뒤에 URL이 사라져 비어버린 라벨 정리
  s = s.replace(/\(?\s*출처\s*[:：]\s*\)?/g, '');
  // 공백/구두점 정리
  s = s.replace(/[ \t]{2,}/g, ' ');
  s = s.replace(/\s+([.,;])/g, '$1');
  s = s.replace(/\n{3,}/g, '\n\n').trim();
  return s || null;
}

/**
 * 기사 원문 등 외부 URL을 앱 내부(인앱 브라우저)에서 연다.
 * - 네이티브(iOS/Android): expo-web-browser의 SFSafariViewController / Custom Tabs
 * - 웹: 새 탭(Linking) 으로 폴백
 * 실패 시 기본 브라우저(Linking)로 폴백한다.
 */
export async function openInAppBrowser(url: string | null | undefined): Promise<void> {
  if (!url) return;
  if (Platform.OS === 'web') {
    await Linking.openURL(url).catch(() => {});
    return;
  }
  try {
    await WebBrowser.openBrowserAsync(url, {
      toolbarColor: colors.surface,
      controlsColor: colors.primary,
      enableBarCollapsing: true,
    });
  } catch {
    // 인앱 브라우저 실패 시 기본 브라우저로 폴백
    await Linking.openURL(url).catch(() => {});
  }
}

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
