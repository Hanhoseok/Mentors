/**
 * 콘텐츠 동 API endpoint wrapper.
 *
 * 백엔드 라우터: backend/features/content/router.py
 * - /api/content/news               (GET, paged + filters)
 * - /api/content/news/search        (GET, RAG semantic)
 * - /api/content/news/{id}          (GET, detail)
 * - /api/content/scraps             (POST/GET/DELETE)
 * - /api/content/keywords           (POST/GET/DELETE)
 * - /api/content/admin/retry-failed (POST)
 *
 * owner: content 동 (5동) — backend
 */

import { apiClient } from '@/api/client';
import type {
  IndustryItem,
  ListNewsParams,
  LiveTopicNewsResponse,
  NewsArticleResponse,
  NewsListResponse,
  RetryFailedResponse,
  ScrapCreateRequest,
  ScrapFolderCreateRequest,
  ScrapFolderResponse,
  ScrapResponse,
  SearchResponse,
  UserKeywordCreateRequest,
  UserKeywordListResponse,
  UserKeywordResponse,
} from './types';

// ---------------------------------------------------------------------------
// 뉴스 피드
// ---------------------------------------------------------------------------

export async function listNews(params: ListNewsParams = {}): Promise<NewsListResponse> {
  const response = await apiClient.get<NewsListResponse>('/api/content/news', { params });
  return response.data;
}

export async function getNewsDetail(newsId: number): Promise<NewsArticleResponse> {
  const response = await apiClient.get<NewsArticleResponse>(`/api/content/news/${newsId}`);
  return response.data;
}

export async function searchNews(query: string, topK = 10): Promise<SearchResponse> {
  const response = await apiClient.get<SearchResponse>('/api/content/news/search', {
    params: { q: query, top_k: topK },
  });
  return response.data;
}

/**
 * 실시간 토픽 뉴스 (SearchScreen 탭용).
 * Google News RSS를 즉석 수집 + OpenAI 일괄 요약. 파이프라인 신뢰도 필터 우회.
 */
export async function fetchLiveTopicNews(
  topic: string,
  limit = 6,
): Promise<LiveTopicNewsResponse> {
  const response = await apiClient.get<LiveTopicNewsResponse>(
    '/api/content/news/live-topics',
    { params: { topic, limit } },
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// 사용자 관심 키워드 CRUD
// ---------------------------------------------------------------------------

export async function listMyKeywords(): Promise<UserKeywordListResponse> {
  const response = await apiClient.get<UserKeywordListResponse>('/api/content/keywords');
  return response.data;
}

export async function addMyKeyword(
  payload: UserKeywordCreateRequest,
): Promise<UserKeywordResponse> {
  const response = await apiClient.post<UserKeywordResponse>('/api/content/keywords', payload);
  return response.data;
}

export async function removeMyKeyword(userKeywordId: number): Promise<void> {
  await apiClient.delete(`/api/content/keywords/${userKeywordId}`);
}

// ---------------------------------------------------------------------------
// 산업 분류 + 하부 키워드 (관심사 설정 카드용)
// ---------------------------------------------------------------------------

export async function listIndustries(): Promise<IndustryItem[]> {
  const response = await apiClient.get<IndustryItem[]>('/api/content/industries');
  return response.data;
}

// ---------------------------------------------------------------------------
// 스크랩
// ---------------------------------------------------------------------------

export async function addScrap(payload: ScrapCreateRequest): Promise<ScrapResponse> {
  const response = await apiClient.post<ScrapResponse>('/api/content/scraps', payload);
  return response.data;
}

export async function listMyScraps(
  params: { folderId?: number; limit?: number } = {},
): Promise<ScrapResponse[]> {
  const { folderId, limit = 100 } = params;
  const response = await apiClient.get<ScrapResponse[]>('/api/content/scraps', {
    params: { limit, ...(folderId != null ? { folder_id: folderId } : {}) },
  });
  return response.data;
}

export async function removeScrap(scrapId: number): Promise<void> {
  await apiClient.delete(`/api/content/scraps/${scrapId}`);
}

/**
 * 특정 기사의 스크랩 여부 단건 조회.
 * 전체 목록을 받아 클라이언트에서 매칭하면 limit 상한(누락)에 걸리므로,
 * 서버가 article_id/url로 직접 EXISTS 판정한다.
 */
export async function checkScrapExists(
  params: { articleId?: number; url?: string } = {},
): Promise<boolean> {
  const { articleId, url } = params;
  if (articleId == null && !url) return false;
  const response = await apiClient.get<{ exists: boolean }>('/api/content/scraps/exists', {
    params: {
      ...(articleId != null ? { article_id: articleId } : {}),
      ...(url ? { url } : {}),
    },
  });
  return response.data.exists;
}

// ---------------------------------------------------------------------------
// 스크랩 폴더 CRUD
// ---------------------------------------------------------------------------

export async function listScrapFolders(): Promise<ScrapFolderResponse[]> {
  const response = await apiClient.get<ScrapFolderResponse[]>('/api/content/scrap-folders');
  return response.data;
}

export async function createScrapFolder(
  payload: ScrapFolderCreateRequest,
): Promise<ScrapFolderResponse> {
  const response = await apiClient.post<ScrapFolderResponse>(
    '/api/content/scrap-folders',
    payload,
  );
  return response.data;
}

export async function removeScrapFolder(folderId: number): Promise<void> {
  await apiClient.delete(`/api/content/scrap-folders/${folderId}`);
}

// ---------------------------------------------------------------------------
// Admin — AI 실패 재처리
// ---------------------------------------------------------------------------

export async function retryFailedAi(limit = 100): Promise<RetryFailedResponse> {
  const response = await apiClient.post<RetryFailedResponse>(
    '/api/content/admin/retry-failed',
    null,
    { params: { limit } },
  );
  return response.data;
}
