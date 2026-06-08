import { useEffect } from 'react';
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { AppIcon } from '@/components/AppIcon';
import {
  useInAppNotificationStore,
  type InAppNotification,
} from '@/store/inAppNotificationStore';
import type { AppStackParamList } from '@/navigation/types';
import { getNotificationTypeIconName } from '@/ui/iconTokens';

type Nav = NavigationProp<AppStackParamList>;

const TYPE_COLOR: Record<string, string> = {
  daily_report: colors.primary,
  promotion_test: '#E6A820',
};

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = Date.now();
  const diff = now - d.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}일 전`;
  return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' });
}

function NotificationCard({
  item,
  onPress,
}: {
  item: InAppNotification;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        !item.read && styles.cardUnread,
        pressed && styles.cardPressed,
      ]}
    >
      <View style={[styles.iconCircle, { backgroundColor: TYPE_COLOR[item.type] + '20' }]}>
        <AppIcon
          color={TYPE_COLOR[item.type] ?? colors.primary}
          name={getNotificationTypeIconName(item.type)}
          size={22}
        />
      </View>
      <View style={styles.cardBody}>
        <View style={styles.cardTop}>
          <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
          {!item.read && <View style={styles.unreadDot} />}
        </View>
        <Text style={styles.cardBody2} numberOfLines={2}>{item.body}</Text>
        <Text style={styles.cardTime}>{formatTime(item.createdAt)}</Text>
      </View>
    </Pressable>
  );
}

export function NotificationsScreen() {
  const navigation = useNavigation<Nav>();
  const notifications = useInAppNotificationStore((s) => s.notifications);
  const markAllRead = useInAppNotificationStore((s) => s.markAllRead);
  const markRead = useInAppNotificationStore((s) => s.markRead);
  const clearAll = useInAppNotificationStore((s) => s.clearAll);

  // 화면 진입 시 모두 읽음 처리
  useEffect(() => {
    markAllRead();
  }, [markAllRead]);

  function handlePress(item: InAppNotification) {
    markRead(item.id);
    if (item.targetScreen === 'DailyReportDetail') {
      navigation.navigate('DailyReportDetail', (item.targetParams ?? {}) as { reportId?: number });
    } else if (item.targetScreen === 'PromotionTest') {
      navigation.navigate('PromotionTest');
    } else if (item.targetScreen === 'LearningRecord') {
      navigation.navigate('LearningRecord');
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>알림</Text>
        {notifications.length > 0 ? (
          <Pressable onPress={clearAll} style={styles.clearBtn}>
            <Text style={styles.clearBtnText}>전체 삭제</Text>
          </Pressable>
        ) : null}
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {notifications.length === 0 ? (
          <View style={styles.emptyBox}>
            <AppIcon color="#A3ACA5" name="bell-off-outline" size={40} />
            <Text style={styles.emptyTitle}>새로운 알림이 없어요</Text>
            <Text style={styles.emptyDesc}>
              일일 리포트 도착, 승급시험 가능 등 주요 이벤트를 여기서 확인할 수 있어요.
            </Text>
          </View>
        ) : (
          notifications.map((item) => (
            <NotificationCard key={item.id} item={item} onPress={() => handlePress(item)} />
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  header: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 8,
    height: 56,
    paddingHorizontal: 16,
  },
  backBtn: { alignItems: 'center', height: 32, justifyContent: 'center', width: 32 },
  backArrow: { color: colors.text, fontSize: 22 },
  headerTitle: { color: colors.text, flex: 1, fontSize: 17, fontWeight: '700' },
  clearBtn: { paddingHorizontal: 6, paddingVertical: 4 },
  clearBtnText: { color: colors.muted, fontSize: 13, fontWeight: '600' },
  scroll: { gap: 1, paddingBottom: 32, paddingTop: 8 },
  card: {
    alignItems: 'flex-start',
    backgroundColor: colors.surface,
    flexDirection: 'row',
    gap: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  cardUnread: {
    backgroundColor: colors.primarySoft,
  },
  cardPressed: { opacity: 0.85 },
  iconCircle: {
    alignItems: 'center',
    borderRadius: 24,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  cardBody: { flex: 1, gap: 3 },
  cardTop: { alignItems: 'center', flexDirection: 'row', gap: 6 },
  cardTitle: { color: colors.text, flex: 1, fontSize: 15, fontWeight: '700' },
  unreadDot: {
    backgroundColor: '#E63946',
    borderRadius: 5,
    height: 8,
    width: 8,
  },
  cardBody2: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  cardTime: { color: '#AFB4B0', fontSize: 11, marginTop: 2 },
  emptyBox: {
    alignItems: 'center',
    gap: 10,
    marginTop: 60,
    paddingHorizontal: 32,
  },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  emptyDesc: { color: colors.muted, fontSize: 13, lineHeight: 19, textAlign: 'center' },
});
