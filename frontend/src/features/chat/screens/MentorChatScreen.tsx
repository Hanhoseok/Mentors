import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type NativeSyntheticEvent,
  type TextInputKeyPressEventData,
} from 'react-native';
import {
  useNavigation,
  useRoute,
  type NavigationProp,
  type RouteProp,
} from '@react-navigation/native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { colors } from '@/constants/colors';
import { AppIcon, IconLabel } from '@/components/AppIcon';
import {
  createLearningChatSession,
  getLearningChatApiErrorMessage,
  listLearningChatMessages,
  listLearningChatSessions,
  streamLearningChat,
} from '@/features/chat/api';
import {
  getLearningChatMentorById,
  learningChatMentors,
  resolveSuggestedLearningMentorId,
} from '@/features/chat/data';
import {
  keepChatScrollPinnedToBottom,
  shouldSubmitChatOnKeyPress,
} from '@/features/chat/logic';
import type { LearningChatFollowUpQuiz, LearningChatMentorId } from '@/features/chat/types';
import {
  getCurrentTierQuizzes,
  getLearningApiErrorMessage,
  getTodayOpener,
  submitLearningQuiz,
} from '@/features/learning/api';
import type {
  SubmitLearningQuizResponse,
  TierQuizCatalogResponse,
} from '@/features/learning/types';
import { stripMarkdown } from '@/features/report/markdown';
import type { GrowthProgressResponse } from '@/features/growth/types';
import { getGrowthProgress } from '@/features/growth/api';
import { useUserStore } from '@/store/userStore';
import {
  applyOptimisticSolvedQuizProgress,
  buildGrowthProgressQueryKey,
} from '@/features/growth/logic';
import { TopIconBar } from '@/features/explore/components/TopIconBar';
import type { AppStackParamList, MainTabParamList } from '@/navigation/types';

type MentorChatRoute = RouteProp<MainTabParamList, 'MentorChat'>;

interface RenderedMessage {
  key: string;
  role: 'user' | 'assistant';
  content: string;
  pending?: boolean;
}

function buildOptimisticQuizCatalog(
  catalog: TierQuizCatalogResponse | undefined,
  conceptId: number,
  correct: boolean,
): TierQuizCatalogResponse | undefined {
  if (!catalog) {
    return catalog;
  }

  return {
    ...catalog,
    quizzes: catalog.quizzes.map((quiz) =>
      quiz.concept_id === conceptId
        ? {
            ...quiz,
            attempted: true,
            solved: quiz.solved || correct,
            last_result_correct: correct,
          }
        : quiz,
    ),
  };
}

export function MentorChatScreen() {
  const navigation = useNavigation<NavigationProp<AppStackParamList>>();
  const route = useRoute<MentorChatRoute>();
  const queryClient = useQueryClient();
  const insets = useSafeAreaInsets();
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    const showEvt = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const hideEvt = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide';
    const showSub = Keyboard.addListener(showEvt, (e) => {
      setKeyboardHeight(e.endCoordinates.height);
    });
    const hideSub = Keyboard.addListener(hideEvt, () => {
      setKeyboardHeight(0);
    });
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);


  const accessToken = useUserStore((state) => state.accessToken);
  const onboardingProfile = useUserStore((state) => state.onboardingProfile);
  const scrollViewRef = useRef<ScrollView | null>(null);

  const [selectedMentorId, setSelectedMentorId] = useState<LearningChatMentorId>(
    () => route.params?.mentorId ?? resolveSuggestedLearningMentorId(onboardingProfile),
  );
  const [activeSessionId, setActiveSessionId] = useState<number | null>(
    route.params?.sessionId ?? null,
  );
  const [draft, setDraft] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);
  const [streamingAssistantText, setStreamingAssistantText] = useState('');
  const [chatErrorMessage, setChatErrorMessage] = useState<string | null>(null);
  const [chatStatusMessage, setChatStatusMessage] = useState<string | null>(null);
  const [followUpQuiz, setFollowUpQuiz] = useState<LearningChatFollowUpQuiz | null>(null);
  const [selectedQuizOptionIndex, setSelectedQuizOptionIndex] = useState<number | null>(null);
  const [quizResult, setQuizResult] = useState<SubmitLearningQuizResponse | null>(null);
  const [quizErrorMessage, setQuizErrorMessage] = useState<string | null>(null);
  const [openerFirstTodayByMentor, setOpenerFirstTodayByMentor] = useState<Record<number, boolean>>(
    {},
  );
  const [dismissedOpenerMentors, setDismissedOpenerMentors] = useState<Record<number, boolean>>({});

  const growthProgressQueryKey = buildGrowthProgressQueryKey(accessToken);
  const learningQuizzesQueryKey = ['learning-quizzes', accessToken] as const;

  const growthQuery = useQuery({
    queryKey: growthProgressQueryKey,
    queryFn: getGrowthProgress,
    enabled: Boolean(accessToken),
    retry: 0,
    staleTime: 60_000,
  });

  const growthProgress = growthQuery.data?.progress_percent ?? 0;
  const growthTier = growthQuery.data?.current_tier ?? 'T1';
  const growthWidth = `${Math.min(growthProgress, 100)}%` as `${number}%`;
  const promotionEligible = growthQuery.data?.eligible_for_promotion === true;
  const promotionNextTier = growthQuery.data?.next_tier ?? null;

  const sessionsQuery = useQuery({
    queryKey: ['learning-chat-sessions', accessToken],
    queryFn: listLearningChatSessions,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const mentorSessions = useMemo(
    () =>
      (sessionsQuery.data?.sessions ?? [])
        .filter((session) => session.mentor_id === selectedMentorId)
        .sort((left, right) => right.created_at.localeCompare(left.created_at)),
    [selectedMentorId, sessionsQuery.data?.sessions],
  );

  const messagesQuery = useQuery({
    queryKey: ['learning-chat-messages', activeSessionId],
    queryFn: () => listLearningChatMessages(activeSessionId as number),
    enabled: Boolean(accessToken) && activeSessionId != null,
    retry: 0,
  });

  const openerQuery = useQuery({
    queryKey: ['learning-today-opener', selectedMentorId, accessToken],
    queryFn: () => getTodayOpener(selectedMentorId),
    enabled: Boolean(accessToken),
    retry: 0,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.data && query.state.data.report.status !== 'ready' ? 2000 : false,
  });

  const createSessionMutation = useMutation({
    mutationFn: createLearningChatSession,
  });

  const submitQuizMutation = useMutation({
    mutationFn: submitLearningQuiz,
    onMutate: (variables) => {
      const previousQuizCatalog =
        queryClient.getQueryData<TierQuizCatalogResponse>(learningQuizzesQueryKey) ?? null;
      const wasSolvedBefore =
        previousQuizCatalog?.quizzes.find((quiz) => quiz.concept_id === variables.concept_id)
          ?.solved ?? false;

      return {
        wasSolvedBefore,
      };
    },
    onSuccess: async (result, variables, context) => {
      setQuizResult(result);
      setQuizErrorMessage(null);

      if (accessToken) {
        queryClient.setQueryData<TierQuizCatalogResponse | undefined>(
          learningQuizzesQueryKey,
          (current) => buildOptimisticQuizCatalog(current, variables.concept_id, result.correct),
        );

        try {
          await queryClient.fetchQuery({
            queryKey: learningQuizzesQueryKey,
            queryFn: getCurrentTierQuizzes,
          });
        } catch {
          // Ignore refresh failures.
        }
      }

      if (!result.correct || !accessToken) {
        if (accessToken) {
          setChatStatusMessage('퀴즈 풀이 기록을 저장했어요.');
        }
        return;
      }

      if (!context?.wasSolvedBefore) {
        queryClient.setQueryData<GrowthProgressResponse | undefined>(
          growthProgressQueryKey,
          (current) => applyOptimisticSolvedQuizProgress(current ?? null) ?? current,
        );
      }

      setChatStatusMessage(
        context?.wasSolvedBefore
          ? '정답을 반영해 최신 퀴즈 상태를 다시 불러왔어요.'
          : '정답이 반영되어 이해도와 개념 퀴즈 상태를 바로 갱신했어요.',
      );

      setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: growthProgressQueryKey });
      }, 1200);
    },
    onError: (error) => {
      setQuizErrorMessage(
        getLearningApiErrorMessage(error, '퀴즈를 제출하지 못했어요. 잠시 후 다시 시도해 주세요.'),
      );
    },
  });

  const selectedMentor = getLearningChatMentorById(selectedMentorId);
  const openerReport = openerQuery.data?.report ?? null;
  const showOpenerCard =
    Boolean(accessToken) &&
    openerFirstTodayByMentor[selectedMentorId] === true &&
    !dismissedOpenerMentors[selectedMentorId] &&
    openerReport != null;
  const isOpenerReportReady = openerReport?.status === 'ready';
  const messageErrorMessage = messagesQuery.error
    ? getLearningChatApiErrorMessage(
        messagesQuery.error,
        '대화 내용을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
      )
    : null;

  useEffect(() => {
    if (route.params?.mentorId) {
      setSelectedMentorId(route.params.mentorId);
    }
    if (route.params?.sessionId) {
      setActiveSessionId(route.params.sessionId);
    }
  }, [route.params?.mentorId, route.params?.sessionId]);

  useEffect(() => {
    if (route.params?.sessionId != null) {
      return;
    }

    if (mentorSessions.length === 0) {
      setActiveSessionId(null);
      return;
    }

    setActiveSessionId((current) => {
      if (current && mentorSessions.some((session) => session.id === current)) {
        return current;
      }
      return mentorSessions[0].id;
    });
  }, [mentorSessions, route.params?.sessionId]);

  useEffect(() => {
    const data = openerQuery.data;
    if (!data) {
      return;
    }
    setOpenerFirstTodayByMentor((prev) =>
      prev[selectedMentorId] === undefined
        ? { ...prev, [selectedMentorId]: data.first_today }
        : prev,
    );
  }, [openerQuery.data, selectedMentorId]);

  useEffect(() => {
    keepChatScrollPinnedToBottom(scrollViewRef.current);
  }, [
    followUpQuiz,
    messagesQuery.data?.messages.length,
    pendingUserMessage,
    streamingAssistantText,
  ]);

  useEffect(() => {
    const eventName = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const subscription = Keyboard.addListener(eventName, () => {
      setTimeout(() => {
        keepChatScrollPinnedToBottom(scrollViewRef.current);
      }, Platform.OS === 'ios' ? 50 : 0);
    });

    return () => {
      subscription.remove();
    };
  }, []);

  const renderedMessages = useMemo<RenderedMessage[]>(() => {
    const baseMessages: RenderedMessage[] = (messagesQuery.data?.messages ?? []).map((message) => ({
      key: `message-${message.id}`,
      role: message.role,
      content: message.content,
    }));

    if (pendingUserMessage) {
      baseMessages.push({
        key: 'pending-user',
        role: 'user',
        content: pendingUserMessage,
        pending: true,
      });
    }

    if (streamingAssistantText || isStreaming) {
      baseMessages.push({
        key: 'pending-assistant',
        role: 'assistant',
        content: streamingAssistantText || '멘토가 답변을 정리하고 있어요. 잠시만 기다려 주세요.',
        pending: true,
      });
    }

    return baseMessages;
  }, [isStreaming, messagesQuery.data?.messages, pendingUserMessage, streamingAssistantText]);

  async function handleSendMessage() {
    const content = draft.trim();
    if (!content || isStreaming) {
      return;
    }

    setChatErrorMessage(null);
    setChatStatusMessage(null);
    setDraft('');
    setPendingUserMessage(content);
    setStreamingAssistantText('');
    setFollowUpQuiz(null);
    setQuizResult(null);
    setQuizErrorMessage(null);
    setSelectedQuizOptionIndex(null);
    setIsStreaming(true);

    let resolvedSessionId = activeSessionId;

    try {
      if (!resolvedSessionId) {
        const createdSession = await createSessionMutation.mutateAsync({
          mentor_id: selectedMentorId,
        });
        resolvedSessionId = createdSession.id;
        setActiveSessionId(createdSession.id);
        await queryClient.invalidateQueries({
          queryKey: ['learning-chat-sessions', accessToken],
        });
      }

      let assistantText = '';
      await streamLearningChat({
        payload: {
          session_id: resolvedSessionId,
          content,
        },
        onEvent: (event) => {
          if (event.type === 'delta') {
            assistantText += event.chunk.delta;
            setStreamingAssistantText((current) => current + event.chunk.delta);
            return;
          }

          setFollowUpQuiz(event.quiz);
          setSelectedQuizOptionIndex(null);
          setQuizResult(null);
        },
      });

      if (assistantText.trim()) {
        setChatStatusMessage('멘토 답변이 도착했어요.');
      } else {
        // 스트림은 정상 종료됐지만 본문이 비어 있음 = 보통 백엔드 LLM 호출 실패.
        setChatErrorMessage(
          '멘토 답변을 생성하지 못했어요. 잠시 후 다시 시도해 주세요. (문제가 계속되면 AI 서버 상태를 확인해 주세요.)',
        );
      }
    } catch (error) {
      setChatErrorMessage(
        getLearningChatApiErrorMessage(
          error,
          '멘토 답변을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
        ),
      );
    } finally {
      if (resolvedSessionId) {
        await queryClient.invalidateQueries({
          queryKey: ['learning-chat-messages', resolvedSessionId],
        });
      }

      setPendingUserMessage(null);
      setStreamingAssistantText('');
      setIsStreaming(false);
    }
  }

  async function handleSelectMentor(nextMentorId: LearningChatMentorId) {
    setSelectedMentorId(nextMentorId);
    setChatErrorMessage(null);
    setChatStatusMessage(null);
    setFollowUpQuiz(null);
    setQuizResult(null);
    setQuizErrorMessage(null);
    setSelectedQuizOptionIndex(null);

    const matchingSession = (sessionsQuery.data?.sessions ?? [])
      .filter((session) => session.mentor_id === nextMentorId)
      .sort((left, right) => right.created_at.localeCompare(left.created_at))[0];

    setActiveSessionId(matchingSession?.id ?? null);
  }

  function handleSubmitFollowUpQuiz() {
    if (!followUpQuiz || selectedQuizOptionIndex == null) {
      setQuizErrorMessage('보기 하나를 고른 뒤 제출해 주세요.');
      return;
    }

    submitQuizMutation.mutate({
      concept_id: followUpQuiz.concept_id,
      answer_index: selectedQuizOptionIndex,
      quiz_index: followUpQuiz.quiz_index,
    });
  }

  function handleComposerKeyPress(
    event: NativeSyntheticEvent<TextInputKeyPressEventData> & { preventDefault?: () => void },
  ) {
    if (Platform.OS !== 'web') {
      return;
    }

    if (
      !shouldSubmitChatOnKeyPress({
        key: event.nativeEvent.key,
        shiftKey: (event.nativeEvent as TextInputKeyPressEventData & { shiftKey?: boolean })
          .shiftKey,
        isComposing: (event.nativeEvent as TextInputKeyPressEventData & { isComposing?: boolean })
          .isComposing,
      })
    ) {
      return;
    }

    event.preventDefault?.();
    void handleSendMessage();
  }

  function handleComposerFocus() {
    // 키보드가 올라오는 동안 여러 번 스크롤해서 입력창/최근 메시지가 항상 보이도록 함
    [60, 180, 350].forEach((delay) => {
      setTimeout(() => {
        keepChatScrollPinnedToBottom(scrollViewRef.current);
      }, delay);
    });
  }

  return (
    <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
      <View
        style={styles.flex}
              >
        {/* 헤더 */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>멘토 채팅</Text>
          <TopIconBar />
        </View>

        {/* 성장 게이지바 */}
        {accessToken ? (
          <View style={styles.growthBar}>
            <Text style={styles.growthTierLabel}>{growthTier} 이해도</Text>
            <View style={styles.growthTrack}>
              <View style={[styles.growthFill, { width: growthWidth }]} />
            </View>
            <Text style={styles.growthPct}>{growthProgress}%</Text>
          </View>
        ) : null}

        {/* 승급시험 응시 배너 — 이해도 80% 이상 충족 시 노출 */}
        {accessToken && promotionEligible && promotionNextTier ? (
          <Pressable
            onPress={() => navigation.navigate('PromotionTest')}
            style={({ pressed }) => [styles.promotionBanner, pressed && styles.pressed]}
          >
            <View style={styles.promotionBannerTextCol}>
              <IconLabel
                color={colors.primary}
                icon="school"
                iconColor={colors.primary}
                iconSize={15}
                label="승급 자격 충족"
                textStyle={styles.promotionBannerEyebrow}
              />
              <Text style={styles.promotionBannerTitle}>
                {promotionNextTier} 승급시험에 응시할 수 있어요
              </Text>
              <Text style={styles.promotionBannerHint}>
                이해도 {growthProgress}% 달성 — 지금 시험으로 다음 티어를 열어보세요.
              </Text>
            </View>
            <Text style={styles.promotionBannerCta}>응시 →</Text>
          </Pressable>
        ) : null}

        <ScrollView
          style={styles.flex}
          contentContainerStyle={[
            styles.scrollContent,
            keyboardHeight > 0 && { paddingBottom: keyboardHeight + 140 },
          ]}
          keyboardShouldPersistTaps="handled"
          ref={scrollViewRef}
          showsVerticalScrollIndicator={false}
        >
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.mentorRow}
          >
            {learningChatMentors.map((mentor) => {
              const selected = mentor.id === selectedMentorId;
              return (
                <Pressable
                  key={mentor.id}
                  onPress={() => {
                    void handleSelectMentor(mentor.id);
                  }}
                  style={({ pressed }) => [
                    styles.mentorCard,
                    { borderColor: selected ? mentor.accentColor : colors.border },
                    selected && { backgroundColor: mentor.avatarTint },
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={[styles.mentorAvatar, { backgroundColor: mentor.avatarTint }]}>
                    <Text style={[styles.mentorAvatarText, { color: mentor.accentColor }]}>
                      {mentor.shortLabel}
                    </Text>
                  </View>
                  <Text style={styles.mentorLabel}>{mentor.label}</Text>
                  <Text style={styles.mentorFocus}>{mentor.focusLabel}</Text>
                </Pressable>
              );
            })}
          </ScrollView>

          <View style={styles.summaryCard}>
            <Text style={[styles.summaryMentor, { color: selectedMentor.accentColor }]}>
              {selectedMentor.label}
            </Text>
            <Text style={styles.summaryDescription}>{selectedMentor.description}</Text>
            <Text style={styles.summaryMeta}>
              {activeSessionId
                ? `이전 세션 #${activeSessionId}에 이어서 학습 중이에요.`
                : '새 세션으로 대화를 시작할 준비가 되어 있어요.'}
            </Text>
          </View>

          {showOpenerCard && openerReport ? (
            <View
              style={[
                styles.openerCard,
                {
                  borderColor: selectedMentor.accentColor,
                  backgroundColor: selectedMentor.avatarTint,
                },
              ]}
            >
              <View style={styles.openerHeaderRow}>
                <Text style={[styles.openerEyebrow, { color: selectedMentor.accentColor }]}>
                  오늘의 일일 리포트
                </Text>
                <Pressable
                  onPress={() =>
                    setDismissedOpenerMentors((prev) => ({ ...prev, [selectedMentorId]: true }))
                  }
                  style={({ pressed }) => [styles.openerCloseBtn, pressed && styles.pressed]}
                >
                  <Text style={styles.openerCloseText}>✕</Text>
                </Pressable>
              </View>

              {openerQuery.data?.opener ? (
                <Text style={[styles.openerGreeting, { color: selectedMentor.accentColor }]}>
                  {openerQuery.data.opener}
                </Text>
              ) : null}

              {isOpenerReportReady && openerReport.body ? (
                <Text style={styles.openerBody} numberOfLines={4}>
                  {stripMarkdown(openerReport.body)}
                </Text>
              ) : (
                <View style={styles.openerSkeleton}>
                  <View style={[styles.skeletonLine, styles.skeletonLineWide]} />
                  <View style={styles.skeletonLine} />
                  <View style={[styles.skeletonLine, styles.skeletonLineNarrow]} />
                  <View style={styles.openerSkeletonHint}>
                    <ActivityIndicator color={selectedMentor.accentColor} size="small" />
                    <Text style={styles.openerSkeletonHintText}>
                      오늘 리포트를 정리하고 있어요.
                    </Text>
                  </View>
                </View>
              )}

              <Pressable
                disabled={!isOpenerReportReady}
                onPress={() =>
                  navigation.navigate('DailyReportDetail', {
                    report: openerReport,
                    opener: openerQuery.data?.opener,
                  })
                }
                style={({ pressed }) => [
                  styles.openerViewButton,
                  { backgroundColor: selectedMentor.accentColor },
                  !isOpenerReportReady && styles.openerViewButtonDisabled,
                  pressed && isOpenerReportReady && styles.pressed,
                ]}
              >
                <Text style={styles.openerViewButtonText}>
                  {isOpenerReportReady ? '전체 리포트 보기' : '리포트 준비 중...'}
                </Text>
              </Pressable>
            </View>
          ) : null}

          {sessionsQuery.isLoading && !activeSessionId ? (
            <View style={styles.stateCard}>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.stateText}>멘토 세션을 확인하고 있어요.</Text>
            </View>
          ) : null}

          {messageErrorMessage ? (
            <View style={styles.stateCard}>
              <Text style={styles.stateTitle}>대화를 불러오지 못했어요</Text>
              <Text style={styles.stateText}>{messageErrorMessage}</Text>
            </View>
          ) : null}

          {renderedMessages.length === 0 && !messagesQuery.isLoading && !messageErrorMessage ? (
            <View style={styles.emptyConversationCard}>
              <Text style={styles.emptyConversationTitle}>
                첫 질문을 보내면 여기서 바로 대화가 이어집니다.
              </Text>
              <Text style={styles.emptyConversationText}>
                예시: PER이 무엇인가요?, 금리 인하가 성장주에 왜 영향을 주나요?
              </Text>
            </View>
          ) : null}

          <View style={styles.messageColumn}>
            {renderedMessages.map((message) => {
              const isUser = message.role === 'user';
              return (
                <View
                  key={message.key}
                  style={[
                    styles.messageRow,
                    isUser ? styles.messageRowUser : styles.messageRowAssistant,
                  ]}
                >
                  {!isUser ? (
                    <Text
                      style={[styles.messageMentorLabel, { color: selectedMentor.accentColor }]}
                    >
                      {selectedMentor.label}
                    </Text>
                  ) : null}
                  <View
                    style={[
                      styles.messageBubble,
                      isUser ? styles.messageBubbleUser : styles.messageBubbleAssistant,
                      message.pending && styles.messageBubblePending,
                    ]}
                  >
                    <Text style={[styles.messageText, isUser && styles.messageTextUser]}>
                      {message.content}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>

          {followUpQuiz ? (
            <View style={styles.quizCard}>
              <Text style={styles.quizEyebrow}>팔로우업 퀴즈</Text>
              <Text style={styles.quizTitle}>{followUpQuiz.question}</Text>
              <Text style={styles.quizMeta}>{followUpQuiz.concept_name} 개념 확인</Text>

              <View style={styles.quizOptionColumn}>
                {followUpQuiz.options.map((option) => {
                  const selected = selectedQuizOptionIndex === option.index;
                  return (
                    <Pressable
                      key={`${followUpQuiz.concept_id}-${option.index}`}
                      onPress={() => {
                        setSelectedQuizOptionIndex(option.index);
                        setQuizErrorMessage(null);
                      }}
                      style={({ pressed }) => [
                        styles.quizOption,
                        selected && styles.quizOptionSelected,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text
                        style={[styles.quizOptionIndex, selected && styles.quizOptionIndexSelected]}
                      >
                        {option.index + 1}
                      </Text>
                      <Text
                        style={[styles.quizOptionText, selected && styles.quizOptionTextSelected]}
                      >
                        {option.text}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>

              {quizErrorMessage ? (
                <Text style={styles.quizErrorText}>{quizErrorMessage}</Text>
              ) : null}
              {quizResult ? (
                <View style={styles.quizResultBox}>
                  <Text style={styles.quizResultTitle}>
                    {quizResult.correct ? '정답입니다.' : '오답이에요. 다시 확인해 보세요.'}
                  </Text>
                  <Text style={styles.quizResultText}>{quizResult.explanation}</Text>
                </View>
              ) : null}

              <Pressable
                disabled={submitQuizMutation.isPending}
                onPress={handleSubmitFollowUpQuiz}
                style={({ pressed }) => [
                  styles.quizSubmitButton,
                  submitQuizMutation.isPending && styles.quizSubmitButtonDisabled,
                  pressed && !submitQuizMutation.isPending && styles.pressed,
                ]}
              >
                <Text style={styles.quizSubmitButtonText}>
                  {submitQuizMutation.isPending ? '제출 중...' : '퀴즈 제출하기'}
                </Text>
              </Pressable>
            </View>
          ) : null}

          {chatStatusMessage ? <Text style={styles.statusText}>{chatStatusMessage}</Text> : null}
          {chatErrorMessage ? <Text style={styles.errorText}>{chatErrorMessage}</Text> : null}
        </ScrollView>

          <View
            style={[
              styles.footer,
              { bottom: keyboardHeight > 0 ? keyboardHeight + 60 : insets.bottom + 76 },
            ]}
          >

          <View style={styles.composer}>
            {/* 학습 기록 버튼 — 입력창 왼쪽 */}
            <Pressable
              onPress={() => navigation.navigate('LearningRecord')}
              style={({ pressed }) => [styles.composerIconBtn, pressed && styles.pressed]}
            >
              <AppIcon color={colors.primary} name="chart-box" size={18} />
            </Pressable>
            <TextInput
              blurOnSubmit={false}
              multiline
              onChangeText={setDraft}
              onContentSizeChange={() => {
                keepChatScrollPinnedToBottom(scrollViewRef.current, false);
              }}
              onFocus={handleComposerFocus}
              onKeyPress={handleComposerKeyPress}
              placeholder="경제 개념이나 시장 흐름에 대해 질문해 보세요"
              placeholderTextColor="#94A096"
              returnKeyType="send"
              style={styles.input}
              value={draft}
            />
            <Pressable
              disabled={!draft.trim() || isStreaming || createSessionMutation.isPending}
              onPress={() => {
                void handleSendMessage();
              }}
              style={({ pressed }) => [
                styles.sendButton,
                (!draft.trim() || isStreaming || createSessionMutation.isPending) &&
                  styles.sendButtonDisabled,
                pressed &&
                  draft.trim() &&
                  !isStreaming &&
                  !createSessionMutation.isPending &&
                  styles.pressed,
              ]}
            >
              <Text style={styles.sendButtonText}>{isStreaming ? '전송 중' : '보내기'}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  flex: {
    flex: 1,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  growthBar: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  growthTierLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    width: 64,
  },
  growthTrack: {
    flex: 1,
    height: 6,
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    overflow: 'hidden',
  },
  growthFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 999,
  },
  growthPct: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '800',
    width: 34,
    textAlign: 'right',
  },
  promotionBanner: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  promotionBannerTextCol: {
    flex: 1,
    gap: 2,
  },
  promotionBannerEyebrow: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.4,
    opacity: 0.92,
  },
  promotionBannerTitle: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '800',
  },
  promotionBannerHint: {
    color: colors.surface,
    fontSize: 12,
    lineHeight: 17,
    opacity: 0.88,
  },
  promotionBannerCta: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '800',
  },
  scrollContent: {
    gap: 16,
    // 떠 있는 입력창(footer) 높이만큼 확보해 마지막 답변이 가리지 않게 함
    paddingBottom: 210,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  mentorRow: {
    gap: 10,
    paddingRight: 12,
  },
  mentorCard: {
    backgroundColor: colors.surface,
    borderRadius: 22,
    borderWidth: 1,
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 14,
    width: 152,
  },
  mentorAvatar: {
    alignItems: 'center',
    borderRadius: 28,
    height: 56,
    justifyContent: 'center',
    width: 56,
  },
  mentorAvatarText: {
    fontSize: 16,
    fontWeight: '800',
  },
  mentorLabel: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '800',
  },
  mentorFocus: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
  },
  summaryCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 8,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  summaryMentor: {
    fontSize: 16,
    fontWeight: '800',
  },
  summaryDescription: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  summaryMeta: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  openerCard: {
    borderRadius: 20,
    borderWidth: 1,
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  openerHeaderRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  openerEyebrow: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  openerCloseBtn: {
    alignItems: 'center',
    height: 24,
    justifyContent: 'center',
    width: 24,
  },
  openerCloseText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '700',
  },
  openerGreeting: {
    fontSize: 15,
    fontWeight: '800',
    lineHeight: 22,
  },
  openerBody: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 21,
  },
  openerSkeleton: {
    gap: 8,
  },
  skeletonLine: {
    backgroundColor: colors.border,
    borderRadius: 6,
    height: 12,
    width: '100%',
  },
  skeletonLineWide: {
    width: '90%',
  },
  skeletonLineNarrow: {
    width: '60%',
  },
  openerSkeletonHint: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  openerSkeletonHintText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  openerViewButton: {
    alignItems: 'center',
    borderRadius: 14,
    justifyContent: 'center',
    paddingVertical: 12,
  },
  openerViewButtonDisabled: {
    opacity: 0.5,
  },
  openerViewButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '800',
  },
  stateCard: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 20,
    borderWidth: 1,
    gap: 8,
    justifyContent: 'center',
    minHeight: 132,
    paddingHorizontal: 24,
  },
  stateTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '800',
  },
  stateText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
  },
  emptyConversationCard: {
    backgroundColor: '#EFF4F0',
    borderRadius: 26,
    gap: 8,
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  emptyConversationTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
  },
  emptyConversationText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  messageColumn: {
    gap: 14,
  },
  messageRow: {
    gap: 8,
  },
  messageRowAssistant: {
    alignItems: 'flex-start',
  },
  messageRowUser: {
    alignItems: 'flex-end',
  },
  messageMentorLabel: {
    fontSize: 12,
    fontWeight: '700',
  },
  messageBubble: {
    borderRadius: 24,
    maxWidth: '86%',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  messageBubbleAssistant: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
  },
  messageBubbleUser: {
    backgroundColor: colors.primary,
  },
  messageBubblePending: {
    opacity: 0.86,
  },
  messageText: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 21,
  },
  messageTextUser: {
    color: colors.surface,
  },
  quizCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 24,
    borderWidth: 1,
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  quizEyebrow: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.6,
  },
  quizTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    lineHeight: 24,
  },
  quizMeta: {
    color: colors.muted,
    fontSize: 12,
  },
  quizOptionColumn: {
    gap: 10,
  },
  quizOption: {
    alignItems: 'flex-start',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  quizOptionSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  quizOptionIndex: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '800',
    width: 16,
  },
  quizOptionIndexSelected: {
    color: colors.primary,
  },
  quizOptionText: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  quizOptionTextSelected: {
    color: colors.primary,
    fontWeight: '700',
  },
  quizErrorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
  },
  quizResultBox: {
    backgroundColor: colors.background,
    borderRadius: 18,
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  quizResultTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '800',
  },
  quizResultText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  quizSubmitButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 16,
    justifyContent: 'center',
    minHeight: 46,
  },
  quizSubmitButtonDisabled: {
    opacity: 0.5,
  },
  quizSubmitButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  statusText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 18,
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
  },
  footer: {
    position: 'absolute',   // ← 추가
    left: 0,                // ← 추가
    right: 0,               // ← 추가
    backgroundColor: 'transparent',
    // marginBottom: 6,     // ← 삭제 (bottom 으로 위치를 잡으므로 불필요)
    paddingBottom: 0,
    paddingHorizontal: 12,
    paddingTop: 8,
  },
  composer: {
    alignItems: 'flex-end',
    // 그림자(=옆쪽 회색 번짐) 제거 + 깔끔한 테두리 선으로 구분
    backgroundColor: colors.surface,
    borderColor: '#D5D9D5',
    borderRadius: 24,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    paddingBottom: 10,
    paddingLeft: 10,
    paddingRight: 10,
    paddingTop: 10,
    shadowOpacity: 0,
    shadowColor: 'transparent',
    elevation: 0,
  },
  composerIconBtn: {
    alignItems: 'center',
    alignSelf: 'flex-end',
    backgroundColor: colors.primarySoft,
    borderRadius: 16,
    height: 38,
    justifyContent: 'center',
    marginBottom: 2,
    width: 38,
  },
  input: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
    maxHeight: 96,
    minHeight: 44,
    paddingVertical: 4,
    textAlignVertical: 'top',
  },
  sendButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 16,
    justifyContent: 'center',
    minHeight: 44,
    minWidth: 72,
    paddingHorizontal: 14,
  },
  sendButtonDisabled: {
    opacity: 0.45,
  },
  sendButtonText: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '800',
  },
  pressed: {
    opacity: 0.88,
  },
});
