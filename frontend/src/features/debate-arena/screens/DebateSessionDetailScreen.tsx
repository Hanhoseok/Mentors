import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
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
import { getDebateSessionDetail } from '../api';
import { useUserStore } from '@/store/userStore';
import type { AppStackParamList } from '@/navigation/types';
import type { DebateTurnType } from '../types';

type RouteProps = RouteProp<AppStackParamList, 'DebateSessionDetail'>;

function turnTypeLabel(type: string): string {
  if (type === 'opinion') return '주장';
  if (type === 'rebuttal') return '반박';
  return '재반박';
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function DebateSessionDetailScreen() {
  const navigation = useNavigation();
  const route = useRoute<RouteProps>();
  const { sessionId } = route.params;
  const accessToken = useUserStore((state) => state.accessToken);

  const detailQuery = useQuery({
    queryKey: ['debate-session-detail', sessionId, accessToken],
    queryFn: () => getDebateSessionDetail(sessionId),
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const session = detailQuery.data;

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <View style={styles.headerTextWrap}>
          <Text style={styles.headerTitle} numberOfLines={1}>
            {session?.topic ?? '토론 기록'}
          </Text>
          {session ? (
            <Text style={styles.headerSubtitle}>
              {session.persona_a_name} vs {session.persona_b_name}
            </Text>
          ) : null}
        </View>
      </View>

      {detailQuery.isLoading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.loadingText}>토론 기록을 불러오고 있어요.</Text>
        </View>
      ) : detailQuery.error ? (
        <View style={styles.loadingBox}>
          <Text style={styles.errorText}>기록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</Text>
        </View>
      ) : session ? (
        <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
          {/* 메타 정보 */}
          <View style={styles.metaCard}>
            <View style={styles.metaRow}>
              <View style={styles.vsBadge}>
                <Text style={styles.vsBadgeText}>
                  {session.persona_a_name} vs {session.persona_b_name}
                </Text>
              </View>
              <Text style={styles.metaDate}>{formatDate(session.created_at)}</Text>
            </View>
            <Text style={styles.topicTitle}>{session.topic}</Text>
            <View style={styles.completedBadge}>
              <Text style={styles.completedBadgeText}>토론 완료</Text>
            </View>
          </View>

          {/* 판단 포인트 */}
          <View style={styles.hintCard}>
            <Text style={styles.hintTitle}>판단 포인트</Text>
            <Text style={styles.hintText}>
              두 멘토가 같은 주제를 어떤 기준으로 다르게 해석했는지 비교해 보세요.
              근거, 시간축, 리스크 기준 중 어느 쪽이 내 판단에 더 설득력 있는지 확인해 보세요.
            </Text>
          </View>

          {/* 턴 목록 */}
          {session.messages.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>저장된 메시지가 없습니다.</Text>
            </View>
          ) : (
            <View style={styles.turnList}>
              {session.messages.map((msg) => {
                const isPersonaA = msg.speaker_id === session.persona_a_id;
                return (
                  <View
                    key={msg.turn_index}
                    style={[
                      styles.turnBubble,
                      isPersonaA ? styles.turnBubblePrimary : styles.turnBubbleAccent,
                    ]}
                  >
                    <View style={styles.turnMetaRow}>
                      <Text
                        style={[
                          styles.turnBadge,
                          isPersonaA ? styles.turnBadgePrimary : styles.turnBadgeAccent,
                        ]}
                      >
                        {msg.speaker_name}
                      </Text>
                      <Text style={styles.turnTypeText}>
                        {turnTypeLabel(msg.turn_type as DebateTurnType)}
                      </Text>
                    </View>
                    <Text style={styles.turnContent}>{msg.content}</Text>
                  </View>
                );
              })}
            </View>
          )}
        </ScrollView>
      ) : null}
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
    minHeight: 56,
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 12,
  },
  backButton: {
    alignItems: 'center',
    height: 32,
    justifyContent: 'center',
    width: 32,
    flexShrink: 0,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '400',
  },
  headerTextWrap: {
    flex: 1,
    gap: 2,
  },
  headerTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '800',
  },
  headerSubtitle: {
    color: colors.muted,
    fontSize: 12,
  },
  loadingBox: {
    alignItems: 'center',
    flex: 1,
    gap: 12,
    justifyContent: 'center',
    padding: 24,
  },
  loadingText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
  },
  errorText: {
    color: colors.rose,
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  content: {
    gap: 14,
    paddingHorizontal: 16,
    paddingTop: 18,
    paddingBottom: 32,
  },
  metaCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 10,
    padding: 16,
  },
  metaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 8,
  },
  vsBadge: {
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  vsBadgeText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  metaDate: {
    color: colors.muted,
    fontSize: 12,
  },
  topicTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
  },
  completedBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  completedBadgeText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '700',
  },
  hintCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    gap: 6,
  },
  hintTitle: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '900',
  },
  hintText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 20,
  },
  emptyBox: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 120,
    padding: 20,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
  },
  turnList: {
    gap: 12,
  },
  turnBubble: {
    borderRadius: 12,
    padding: 16,
  },
  turnBubblePrimary: {
    backgroundColor: colors.primarySoft,
  },
  turnBubbleAccent: {
    backgroundColor: colors.accentSoft,
  },
  turnMetaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 10,
  },
  turnBadge: {
    borderRadius: 6,
    color: colors.surface,
    fontSize: 12,
    fontWeight: '900',
    overflow: 'hidden',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  turnBadgePrimary: {
    backgroundColor: colors.primary,
  },
  turnBadgeAccent: {
    backgroundColor: '#E6A820',
  },
  turnTypeText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '800',
  },
  turnContent: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 24,
  },
});
