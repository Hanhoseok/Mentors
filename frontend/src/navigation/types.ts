import type { NavigatorScreenParams } from '@react-navigation/native';
import type { LearningChatMentorId } from '@/features/chat/types';

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
};

declare global {
  namespace ReactNavigation {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface RootParamList extends AppStackParamList {}
  }
}
