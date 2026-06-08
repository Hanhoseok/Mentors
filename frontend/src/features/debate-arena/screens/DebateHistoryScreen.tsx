import { useNavigation, type NavigationProp } from '@react-navigation/native';
import { useQuery } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { IconLabel } from '@/components/AppIcon';
import { listDebateSessions } from '../api';
import { useUserStore } from '@/store/userStore';
import type { AppStackParamList } from '@/navigation/types';

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = Date.now();
  const diff = now - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  if (days === 0) return '오늘';
  if (days === 1) return '어제';
  if (days < 7) return `${days}일 전`;
  return date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' });
}

export function DebateHistoryScreen() {
  const navigation = useNavigation<NavigationProp<AppStackParamList>>();
  const accessToken = useUserStore((state) => state.accessToken);

  const sessionsQuery = useQuery({
    queryKey: ['debate-sessions', accessToken],
    queryFn: listDebateSessions,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const sessions = sessionsQuery.data?.sessions ?? [];

  function handleOpenSession(sessionId: number) {
    navigation.navigate('DebateSessionDetail', { sessionId });
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>투기장 기록</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Text style={styles.heroEyebrow}>투기장 기록</Text>
          <Text style={styles.heroTitle}>완료된 토론을 다시 볼 수 있어요</Text>
          <Text style={styles.heroDescription}>
            토론이 완료된 기록을 카드로 모았어요. 누르면 두 멘토의 대화를 다시 확인할 수 있어요.
          </Text>
        </View>

        {sessionsQuery.isLoading ? (
          <View style={styles.stateCard}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.stateText}>투기장 기록을 불러오고 있어요.</Text>
          </View>
        ) : null}

        {!sessionsQuery.isLoading && sessionsQuery.error ? (
          <View style={styles.stateCard}>
            <Text style={styles.stateTitle}>기록을 불러오지 못했어요</Text>
            <Text style={styles.stateText}>잠시 후 다시 시도해 주세요.</Text>
          </View>
        ) : null}

        {!sessionsQuery.isLoading && !sessionsQuery.error && sessions.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>아직 완료된 토론이 없어요</Text>
            <Text style={styles.emptyDescription}>
              투기장 탭에서 두 멘토의 토론을 진행하면 여기에 기록이 남아요.
            </Text>
          </View>
        ) : null}

        {!sessionsQuery.isLoading && !sessionsQuery.error
          ? sessions.map((session, index) => (
              <Pressable
                key={session.id}
                onPress={() => handleOpenSession(session.id)}
                style={({ pressed }) => [
                  styles.historyCard,
                  index % 2 === 1 && styles.historyCardOffset,
                  pressed && styles.historyCardPressed,
                ]}
              >
                <View style={styles.notch} />
                <View style={styles.historyHeader}>
                  <View style={styles.vsBadge}>
                    <Text style={styles.vsBadgeText}>
                      {session.persona_a_name} vs {session.persona_b_name}
                    </Text>
                  </View>
                  <Text style={styles.historyDate}>{formatDate(session.created_at)}</Text>
                </View>
                <Text style={styles.historyTopic}>{session.topic}</Text>
                <View style={styles.historyFooter}>
                  <Text style={styles.historyStatus}>토론 완료</Text>
                  <IconLabel
                    color={colors.primary}
                    icon="open-in-new"
                    iconColor={colors.primary}
                    iconSize={14}
                    label="다시 보기"
                    textStyle={styles.historyOpen}
                  />
                </View>
              </Pressable>
            ))
          : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    height: 56,
    paddingHorizontal: 16,
    gap: 8,
  },
  backButton: {
    alignItems: 'center',
    height: 32,
    justifyContent: 'center',
    width: 32,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '400',
  },
  headerTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  scrollContent: {
    gap: 16,
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 32,
  },
  hero: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 8,
    paddingHorizontal: 20,
    paddingVertical: 20,
  },
  heroEyebrow: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.6,
  },
  heroTitle: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '800',
    lineHeight: 30,
  },
  heroDescription: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  stateCard: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 10,
    justifyContent: 'center',
    minHeight: 180,
    paddingHorizontal: 24,
  },
  stateTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  stateText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
  },
  emptyCard: {
    backgroundColor: '#F2F3F2',
    borderRadius: 28,
    gap: 10,
    justifyContent: 'center',
    minHeight: 176,
    paddingHorizontal: 24,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '800',
  },
  emptyDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  historyCard: {
    backgroundColor: colors.primarySoft,
    borderRadius: 28,
    gap: 12,
    minHeight: 160,
    overflow: 'hidden',
    paddingHorizontal: 22,
    paddingVertical: 20,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.14,
    shadowRadius: 18,
  },
  historyCardOffset: {
    marginLeft: 8,
  },
  historyCardPressed: {
    opacity: 0.92,
  },
  notch: {
    position: 'absolute',
    left: -10,
    top: 20,
    width: 24,
    height: 40,
    borderTopRightRadius: 20,
    borderBottomRightRadius: 20,
    backgroundColor: colors.primary,
  },
  historyHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  vsBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  vsBadgeText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  historyDate: {
    color: colors.muted,
    fontSize: 12,
  },
  historyTopic: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
    flex: 1,
  },
  historyFooter: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  historyStatus: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  historyOpen: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
});
