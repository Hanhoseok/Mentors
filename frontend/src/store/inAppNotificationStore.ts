/**
 * 앱 내 알림(인앱 알림) 스토어.
 *
 * 이벤트:
 *   - 'daily_report'  : 일일 리포트 도착
 *   - 'promotion_test': 승급시험 가능
 *
 * 빨간 점 표시: unreadCount > 0 일 때 알림 아이콘에 배지를 띄운다.
 * 알림 탭 진입 시: markAllRead() 호출 → unreadCount = 0.
 *
 * ⚠️ 계정 격리:
 *   - accessToken이 변경될 때마다 알림을 초기화한다.
 *   - 로그아웃 → clearAll() (AsyncStorage도 지움)
 *   - 새 로그인 → 메모리 초기화 (이전 계정 알림이 보이지 않음)
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { useUserStore } from '@/store/userStore';

export type InAppNotificationType = 'daily_report' | 'promotion_test';

export interface InAppNotification {
  id: string;
  type: InAppNotificationType;
  title: string;
  body: string;
  createdAt: string; // ISO-8601
  read: boolean;
  /** 탭 시 이동할 화면 식별자 (옵션) */
  targetScreen?: string;
  /** 화면 파라미터 */
  targetParams?: Record<string, unknown>;
}

interface InAppNotificationState {
  notifications: InAppNotification[];
  unreadCount: number;
  hydrated: boolean;
  /** 알림 추가 (중복 방지: 같은 type+날짜의 알림은 하루에 한 번만) */
  addNotification: (n: Omit<InAppNotification, 'id' | 'read' | 'createdAt'>) => void;
  /** 모든 알림을 읽음 처리 */
  markAllRead: () => void;
  /** 특정 알림 읽음 처리 */
  markRead: (id: string) => void;
  /** 전체 삭제 (AsyncStorage 포함) */
  clearAll: () => void;
}

const STORAGE_KEY = 'mentors-inapp-notifications';
const MAX_NOTIFICATIONS = 50;

function computeUnread(notifications: InAppNotification[]): number {
  return notifications.filter((n) => !n.read).length;
}

async function persist(notifications: InAppNotification[]): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(notifications));
  } catch {
    // ignore
  }
}

export const useInAppNotificationStore = create<InAppNotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  hydrated: false,

  addNotification: (n) => {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    const existing = get().notifications;

    // 같은 타입의 오늘 알림이 이미 있으면 중복 추가 안 함
    const duplicate = existing.some(
      (item) => item.type === n.type && item.createdAt.startsWith(today),
    );
    if (duplicate) return;

    const newItem: InAppNotification = {
      ...n,
      id: `${n.type}-${Date.now()}`,
      read: false,
      createdAt: new Date().toISOString(),
    };

    const next = [newItem, ...existing].slice(0, MAX_NOTIFICATIONS);
    set({ notifications: next, unreadCount: computeUnread(next) });
    void persist(next);
  },

  markAllRead: () => {
    const next = get().notifications.map((n) => ({ ...n, read: true }));
    set({ notifications: next, unreadCount: 0 });
    void persist(next);
  },

  markRead: (id) => {
    const next = get().notifications.map((n) => (n.id === id ? { ...n, read: true } : n));
    set({ notifications: next, unreadCount: computeUnread(next) });
    void persist(next);
  },

  clearAll: () => {
    set({ notifications: [], unreadCount: 0 });
    void AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
  },
}));

// ── 계정 전환 감지: accessToken이 바뀌면 알림 초기화 ─────────────────────────
// 로그아웃(null) → clearAll: AsyncStorage까지 삭제
// 신규 로그인(새 토큰) → 메모리 초기화: 이전 계정 알림이 화면에 남지 않음
useUserStore.subscribe((state, prevState) => {
  if (state.accessToken === prevState.accessToken) return;

  if (!state.accessToken) {
    // 로그아웃
    useInAppNotificationStore.getState().clearAll();
  } else {
    // 새 계정 로그인: 메모리만 초기화(AsyncStorage는 새 알림으로 덮어쓰기됨)
    useInAppNotificationStore.setState({ notifications: [], unreadCount: 0, hydrated: true });
  }
});

// 앱 시작 시 AsyncStorage에서 복원 (첫 세션 또는 동일 계정 재진입)
void AsyncStorage.getItem(STORAGE_KEY)
  .then((stored) => {
    // 이미 로그인 구독이 처리했다면 덮어쓰지 않음
    if (useInAppNotificationStore.getState().hydrated) return;
    if (!stored) {
      useInAppNotificationStore.setState({ hydrated: true });
      return;
    }
    const parsed = JSON.parse(stored) as InAppNotification[];
    const valid = Array.isArray(parsed) ? parsed : [];
    useInAppNotificationStore.setState({
      notifications: valid,
      unreadCount: computeUnread(valid),
      hydrated: true,
    });
  })
  .catch(() => {
    useInAppNotificationStore.setState({ hydrated: true });
  });
