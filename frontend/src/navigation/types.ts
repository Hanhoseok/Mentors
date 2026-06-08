import type { NavigatorScreenParams } from '@react-navigation/native';
import type { LearningChatMentorId } from '@/features/chat/types';
import type { DailyReportCard } from '@/features/learning/types';

export type MainTabParamList = {
  Search: undefined;
  MentorChat:
    | {
        sessionId?: number;
        mentorId?: LearningChatMentorId;
      }
    | undefined;
  DebateArena:
    | {
        replaySessionId?: number;
        replayStreamUrl?: string;
        replayTopic?: string;
        replayPersonaAName?: string;
        replayPersonaBName?: string;
      }
    | undefined;
};

export type AppStackParamList = {
  Login: undefined;
  Signup: undefined;
  Onboarding: undefined;
  MainTabs: NavigatorScreenParams<MainTabParamList> | undefined;
  LearningRecord: undefined;
  PromotionTest: undefined;
  PromotionResult: undefined;
  InterestSettings: undefined;
  ChatHistory: undefined;
  DebateHistory: undefined;
  DebateSessionDetail: { sessionId: number };
  SearchResult: { query: string };
  /** 앱 내부 WebView 브라우저 — 원문 기사를 본문 영역 크기로 표시 */
  InAppBrowser: { url: string; title?: string };
  RssArticleSummary: {
    title: string;
    url: string;
    source_name: string | null;
    published_at: string | null;
    /** 파이프라인 기사 ID — 있으면 본문/요약/이미지를 DB에서 조회 */
    article_id?: number;
    /** 카드에 이미 노출된 썸네일 — 없으면 이후 detail에서 채워짐 */
    image_url?: string | null;
    /** AI 요약(summary_ko) 프리로드 — 없으면 detail에서 조회 */
    summary?: string | null;
    /** 본문 한국어 번역본 프리로드 — 없으면 detail에서 조회 */
    content?: string | null;
  };
  Settings: undefined;
  NotificationSettings: undefined;
  AccountSettings: undefined;
  NewsDetail: {
    newsId: number;
  };
  Scrap: undefined;
  ScrapFolder: {
    folderId: number;
    folderName: string;
  };
  Notifications: undefined;
  DailyReportDetail: {
    report?: DailyReportCard;
    reportId?: number;
    opener?: string;
  };
};

declare global {
  namespace ReactNavigation {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface RootParamList extends AppStackParamList {}
  }
}
