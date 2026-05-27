import { useMemo } from 'react';
import { useNavigation, type NavigationProp } from '@react-navigation/native';
import { useQueries, useQuery } from '@tanstack/react-query';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import {
  getLearningChatApiErrorMessage,
  listLearningChatMessages,
  listLearningChatSessions,
} from '@/features/chat/api';
import { buildLearningChatHistoryCards } from '@/features/chat/logic';
import { useUserStore } from '@/store/userStore';
import type { RootStackParamList } from '../navigation/types';

export function ChatHistoryScreen() {
  const navigation = useNavigation<NavigationProp<RootStackParamList>>();
  const accessToken = useUserStore((state) => state.accessToken);

  const sessionsQuery = useQuery({
    queryKey: ['learning-chat-sessions', accessToken],
    queryFn: listLearningChatSessions,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const messageQueries = useQueries({
    queries: (sessionsQuery.data?.sessions ?? []).map((session) => ({
      queryKey: ['learning-chat-messages', session.id],
      queryFn: () => listLearningChatMessages(session.id),
      enabled: Boolean(accessToken),
      retry: 0,
    })),
  });

  const historyCards = useMemo(() => {
    const messagesBySessionId = Object.fromEntries(
      (sessionsQuery.data?.sessions ?? []).map((session, index) => [
        session.id,
        messageQueries[index]?.data?.messages ?? [],
      ]),
    );

    return buildLearningChatHistoryCards(sessionsQuery.data?.sessions ?? [], messagesBySessionId);
  }, [messageQueries, sessionsQuery.data?.sessions]);

  const isLoading = sessionsQuery.isLoading || messageQueries.some((query) => query.isLoading);
  const errorMessage = sessionsQuery.error
    ? getLearningChatApiErrorMessage(
        sessionsQuery.error,
        '채팅 기록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      )
    : null;

  function handleOpenSession(sessionId: number, mentorId: number) {
    navigation.navigate('Home', {
      screen: 'MentorChat',
      params: {
        sessionId,
        mentorId: mentorId as 1 | 2 | 3 | 4,
      },
    });
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Text style={styles.heroEyebrow}>채팅 기록</Text>
          <Text style={styles.heroTitle}>이전 멘토 대화를 다시 이어갈 수 있어요</Text>
          <Text style={styles.heroDescription}>
            최근 세션을 카드로 묶어 두었어요. 원하는 대화를 누르면 같은 멘토와 바로 이어서 학습할 수
            있어요.
          </Text>
        </View>

        {isLoading ? (
          <View style={styles.stateCard}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.stateText}>채팅 기록을 정리하고 있어요.</Text>
          </View>
        ) : null}

        {!isLoading && errorMessage ? (
          <View style={styles.stateCard}>
            <Text style={styles.stateTitle}>기록을 불러오지 못했어요</Text>
            <Text style={styles.stateText}>{errorMessage}</Text>
          </View>
        ) : null}

        {!isLoading && !errorMessage && historyCards.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>아직 저장된 채팅이 없어요</Text>
            <Text style={styles.emptyDescription}>
              멘토 탭에서 첫 질문을 보내면 여기에서 이전 대화를 바로 다시 열 수 있어요.
            </Text>
          </View>
        ) : null}

        {!isLoading && !errorMessage
          ? historyCards.map((card, index) => (
              <Pressable
                key={card.sessionId}
                onPress={() => handleOpenSession(card.sessionId, card.mentor.id)}
                style={({ pressed }) => [
                  styles.historyCard,
                  index % 2 === 1 && styles.historyCardOffset,
                  pressed && styles.historyCardPressed,
                ]}
              >
                <View style={[styles.notch, { backgroundColor: card.mentor.avatarTint }]} />
                <View style={styles.historyHeader}>
                  <View style={styles.historyMentorBadge}>
                    <Text style={[styles.historyMentorText, { color: card.mentor.accentColor }]}>
                      {card.mentor.label}
                    </Text>
                  </View>
                  <Text style={styles.historyDate}>{card.createdAtLabel}</Text>
                </View>
                <Text style={styles.historyTitle}>{card.title}</Text>
                <Text style={styles.historyPreview}>{card.preview}</Text>
                <View style={styles.historyFooter}>
                  <Text style={styles.historyCount}>메시지 {card.messageCount}개</Text>
                  <Text style={styles.historyOpen}>열기 ↗</Text>
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
    backgroundColor: '#F5F5F5',
    borderRadius: 28,
    gap: 12,
    minHeight: 176,
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
  },
  historyHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  historyMentorBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.surface,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  historyMentorText: {
    fontSize: 12,
    fontWeight: '700',
  },
  historyDate: {
    color: colors.muted,
    fontSize: 12,
  },
  historyTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
  },
  historyPreview: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
    minHeight: 58,
  },
  historyFooter: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  historyCount: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  historyOpen: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
});
