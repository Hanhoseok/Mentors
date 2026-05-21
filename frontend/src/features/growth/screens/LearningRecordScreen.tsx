import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { getGrowthApiErrorMessage, getGrowthProgress } from '@/features/growth/api';
import { GrowthProgressCard } from '@/features/growth/components/GrowthProgressCard';
import {
  getCurrentTierQuizzes,
  getLearningApiErrorMessage,
  submitLearningQuiz,
} from '@/features/learning/api';
import type {
  LearningQuiz,
  SubmitLearningQuizRequest,
  SubmitLearningQuizResponse,
} from '@/features/learning/types';
import type { RootStackParamList } from '@/navigation/types';
import { useUserStore } from '@/store/userStore';
import {
  arenaRecords,
  reportRecords,
  type ArenaRecord,
  type ReportUnderstanding,
} from '../data';
import {
  didGrowthProgressAdvance,
  getLearningRecordHintMessage,
  getLearningRecordSegments,
  type LearningRecordSegmentKey,
} from '../logic';
import type { GrowthProgressResponse } from '../types';

type LearningRecordScreenProps = NativeStackScreenProps<RootStackParamList, 'Home'>;
type QuizResultTone = 'correct' | 'incorrect' | 'review';

interface QuizSubmissionState {
  correct: boolean;
  explanation: string;
  syncState: 'idle' | 'syncing' | 'synced' | 'delayed';
  message: string | null;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function getQuizResultState(
  submissionState: QuizSubmissionState | undefined,
): { label: string; tone: QuizResultTone } {
  if (!submissionState) {
    return { label: '풀어보기', tone: 'review' };
  }

  if (!submissionState.correct) {
    return { label: '다시 도전', tone: 'incorrect' };
  }

  if (submissionState.syncState === 'syncing') {
    return { label: '정답 · 반영 중', tone: 'review' };
  }

  if (submissionState.syncState === 'delayed') {
    return { label: '정답 · 확인 필요', tone: 'review' };
  }

  return { label: '정답', tone: 'correct' };
}

function ReportCard({
  mentor,
  date,
  title,
  summary,
  understanding,
  onSelectUnderstanding,
}: {
  mentor: string;
  date: string;
  title: string;
  summary: string;
  understanding: ReportUnderstanding;
  onSelectUnderstanding: (next: ReportUnderstanding) => void;
}) {
  const understandingOptions: {
    value: ReportUnderstanding;
    label: string;
    icon: string;
  }[] = [
    { value: 'known', label: '알고 있어요', icon: '✓' },
    { value: 'heard', label: '들어봤어요', icon: '💭' },
    { value: 'unknown', label: '모르겠어요', icon: '?' },
  ];

  return (
    <View style={styles.card}>
      <View style={styles.cardHeaderRow}>
        <Text style={styles.reportMentor}>{mentor}</Text>
        <Text style={styles.cardDate}>{date}</Text>
      </View>
      <Text style={styles.reportTitle}>{title}</Text>
      <Text style={styles.reportSummary}>{summary}</Text>
      <View style={styles.reportChips}>
        {understandingOptions.map((option) => {
          const selected = understanding === option.value;
          return (
            <Pressable
              key={option.value}
              onPress={() => onSelectUnderstanding(option.value)}
              style={[
                styles.reportChip,
                selected ? styles.reportChipSelected : styles.reportChipIdle,
              ]}
            >
              <Text style={[styles.reportChipText, selected && styles.reportChipTextSelected]}>
                {option.icon} {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function QuizResultChip({ label, tone }: { label: string; tone: QuizResultTone }) {
  const toneStyle =
    tone === 'correct'
      ? styles.quizResultChipCorrect
      : tone === 'incorrect'
        ? styles.quizResultChipIncorrect
        : styles.quizResultChipReview;

  const toneTextStyle =
    tone === 'correct'
      ? styles.quizResultChipTextCorrect
      : tone === 'incorrect'
        ? styles.quizResultChipTextIncorrect
        : styles.quizResultChipTextReview;

  return (
    <View style={[styles.quizResultChip, toneStyle]}>
      <Text style={[styles.quizResultChipText, toneTextStyle]}>{label}</Text>
    </View>
  );
}

function QuizCard({
  quiz,
  tierLabel,
  expanded,
  selectedAnswerIndex,
  submissionState,
  errorMessage,
  isSubmitting,
  onToggle,
  onSelectAnswer,
  onSubmit,
}: {
  quiz: LearningQuiz;
  tierLabel: string;
  expanded: boolean;
  selectedAnswerIndex: number | undefined;
  submissionState: QuizSubmissionState | undefined;
  errorMessage: string | undefined;
  isSubmitting: boolean;
  onToggle: () => void;
  onSelectAnswer: (answerIndex: number) => void;
  onSubmit: () => void;
}) {
  const resultState = getQuizResultState(submissionState);

  return (
    <View style={[styles.card, styles.quizCard, expanded && styles.quizCardExpanded]}>
      <Pressable onPress={onToggle} style={styles.quizCardToggle}>
        <View style={styles.quizIndicator}>
          <Text style={styles.quizIndicatorText}>🧠</Text>
        </View>
        <View style={styles.quizBody}>
          <Text style={styles.quizMeta}>{tierLabel}</Text>
          <Text style={styles.quizConcept}>{quiz.concept_name}</Text>
          <Text style={styles.quizQuestion}>{quiz.question}</Text>
          <QuizResultChip label={resultState.label} tone={resultState.tone} />
        </View>
        <Text style={styles.quizArrow}>{expanded ? '⌄' : '›'}</Text>
      </Pressable>

      {expanded ? (
        <View style={styles.quizDetail}>
          <View style={styles.quizOptionList}>
            {quiz.options.map((option) => {
              const selected = selectedAnswerIndex === option.index;
              return (
                <Pressable
                  key={option.index}
                  onPress={() => onSelectAnswer(option.index)}
                  style={({ pressed }) => [
                    styles.quizOptionButton,
                    selected ? styles.quizOptionButtonSelected : styles.quizOptionButtonIdle,
                    pressed && styles.quizOptionButtonPressed,
                  ]}
                >
                  <Text style={[styles.quizOptionIndex, selected && styles.quizOptionIndexSelected]}>
                    {option.index + 1}
                  </Text>
                  <Text style={[styles.quizOptionText, selected && styles.quizOptionTextSelected]}>
                    {option.text}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {errorMessage ? <Text style={styles.quizErrorText}>{errorMessage}</Text> : null}

          {submissionState ? (
            <View style={styles.quizExplanationBox}>
              <Text style={styles.quizExplanationTitle}>
                {submissionState.correct ? '정답 해설' : '오답 해설'}
              </Text>
              <Text style={styles.quizExplanationText}>{submissionState.explanation}</Text>
              {submissionState.message ? (
                <Text style={styles.quizSyncText}>{submissionState.message}</Text>
              ) : null}
            </View>
          ) : null}

          <Pressable
            onPress={onSubmit}
            disabled={selectedAnswerIndex == null || isSubmitting}
            style={({ pressed }) => [
              styles.quizSubmitButton,
              (selectedAnswerIndex == null || isSubmitting) && styles.quizSubmitButtonDisabled,
              pressed &&
                selectedAnswerIndex != null &&
                !isSubmitting &&
                styles.quizSubmitButtonPressed,
            ]}
          >
            <Text style={styles.quizSubmitButtonText}>
              {isSubmitting ? '채점 중...' : '정답 제출하기'}
            </Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function ArenaAvatar({ letter, label }: { letter: string; label: string }) {
  return (
    <View style={styles.avatarColumn}>
      <View style={styles.avatarOuter}>
        <View style={styles.avatarInner}>
          <Text style={styles.avatarLetter}>{letter}</Text>
        </View>
      </View>
      <Text style={styles.avatarLabel}>{label}</Text>
    </View>
  );
}

function ArenaCard({
  date,
  topicLabel,
  topic,
  mentorALetter,
  mentorBLetter,
  mentorALabel,
  mentorBLabel,
}: ArenaRecord) {
  return (
    <Pressable style={[styles.card, styles.arenaCard]}>
      <View style={styles.arenaAvatarRow}>
        <ArenaAvatar letter={mentorALetter} label={mentorALabel} />
        <Text style={styles.arenaVs}>VS</Text>
        <ArenaAvatar letter={mentorBLetter} label={mentorBLabel} />
      </View>
      <Text style={styles.cardDate}>{date}</Text>
      <Text style={styles.arenaTopicLabel}>{topicLabel}</Text>
      <Text style={styles.arenaTopic}>{topic}</Text>
      <Text style={styles.quizArrow}>›</Text>
    </Pressable>
  );
}

function InfoCard({ title, description }: { title: string; description: string }) {
  return (
    <View style={[styles.card, styles.infoCard]}>
      <Text style={styles.infoTitle}>{title}</Text>
      <Text style={styles.infoDescription}>{description}</Text>
    </View>
  );
}

function BottomNavMock() {
  return (
    <View style={styles.bottomNav}>
      <View style={styles.bottomNavDivider} />
      <View style={styles.bottomNavTabs}>
        <View style={styles.bottomNavTab}>
          <Text style={styles.bottomNavIcon}>🔍</Text>
          <Text style={styles.bottomNavLabel}>탐색</Text>
        </View>
        <View style={[styles.bottomNavTab, styles.bottomNavTabActive]}>
          <Text style={styles.bottomNavIcon}>💬</Text>
          <Text style={[styles.bottomNavLabel, styles.bottomNavLabelActive]}>채팅</Text>
        </View>
        <View style={styles.bottomNavTab}>
          <Text style={styles.bottomNavIcon}>⚔️</Text>
          <Text style={styles.bottomNavLabel}>투기장</Text>
        </View>
      </View>
      <View style={styles.homeIndicator} />
    </View>
  );
}

export function LearningRecordScreen({ navigation }: LearningRecordScreenProps) {
  const accessToken = useUserStore((state) => state.accessToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);
  const queryClient = useQueryClient();
  const [selectedSegment, setSelectedSegment] = useState<LearningRecordSegmentKey>('reports');
  const [expandedQuizConceptId, setExpandedQuizConceptId] = useState<number | null>(null);
  const [selectedAnswerByConceptId, setSelectedAnswerByConceptId] = useState<
    Record<number, number | undefined>
  >({});
  const [quizSubmissionByConceptId, setQuizSubmissionByConceptId] = useState<
    Record<number, QuizSubmissionState>
  >({});
  const [quizErrorByConceptId, setQuizErrorByConceptId] = useState<Record<number, string>>({});
  const [understandingByRecordId, setUnderstandingByRecordId] = useState<
    Record<string, ReportUnderstanding>
  >(
    () =>
      Object.fromEntries(
        reportRecords.map((record) => [record.id, record.understanding]),
      ) as Record<string, ReportUnderstanding>,
  );

  const growthQueryKey = ['growth-progress', accessToken] as const;
  const growthProgressQuery = useQuery({
    queryKey: growthQueryKey,
    queryFn: getGrowthProgress,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const learningQuizzesQuery = useQuery({
    queryKey: ['learning-quizzes', accessToken],
    queryFn: getCurrentTierQuizzes,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const submitQuizMutation = useMutation<
    SubmitLearningQuizResponse,
    unknown,
    SubmitLearningQuizRequest,
    { previousGrowthProgress: GrowthProgressResponse | null }
  >({
    mutationFn: submitLearningQuiz,
    onMutate: (variables) => {
      setQuizErrorByConceptId((current) => ({
        ...current,
        [variables.concept_id]: '',
      }));

      return {
        previousGrowthProgress: growthProgressQuery.data ?? null,
      };
    },
    onSuccess: async (result, variables, context) => {
      const initialState: QuizSubmissionState = {
        correct: result.correct,
        explanation: result.explanation,
        syncState: result.correct ? 'syncing' : 'idle',
        message: result.correct
          ? '정답이에요. 성장 게이지 반영을 확인하고 있어요.'
          : '오답이에요. 해설을 확인하고 다시 도전해 보세요.',
      };

      setQuizSubmissionByConceptId((current) => ({
        ...current,
        [variables.concept_id]: initialState,
      }));

      if (!result.correct) {
        return;
      }

      let nextState: QuizSubmissionState = {
        ...initialState,
        syncState: 'delayed',
        message: '정답은 저장됐어요. 성장 게이지 반영은 서버 동기화에 따라 잠시 늦을 수 있어요.',
      };

      try {
        const previousGrowthProgress = context?.previousGrowthProgress ?? null;

        if (!previousGrowthProgress) {
          await queryClient.invalidateQueries({ queryKey: growthQueryKey });
          nextState = {
            ...initialState,
            syncState: 'synced',
            message: '정답을 저장하고 성장 카드를 새로고침했어요.',
          };
        } else {
          for (let attempt = 0; attempt < 3; attempt += 1) {
            const nextProgress = await queryClient.fetchQuery({
              queryKey: growthQueryKey,
              queryFn: getGrowthProgress,
            });

            if (didGrowthProgressAdvance(previousGrowthProgress, nextProgress)) {
              nextState = {
                ...initialState,
                syncState: 'synced',
                message: '정답이 반영되어 성장 게이지를 갱신했어요.',
              };
              break;
            }

            await wait(450);
          }

          await queryClient.invalidateQueries({ queryKey: growthQueryKey });
        }
      } catch {
        await queryClient.invalidateQueries({ queryKey: growthQueryKey });
      }

      setQuizSubmissionByConceptId((current) => ({
        ...current,
        [variables.concept_id]: nextState,
      }));
    },
    onError: (error, variables) => {
      setQuizErrorByConceptId((current) => ({
        ...current,
        [variables.concept_id]: getLearningApiErrorMessage(
          error,
          '퀴즈 제출에 실패했어요. 잠시 후 다시 시도해 주세요.',
        ),
      }));
    },
  });

  const growthErrorMessage = growthProgressQuery.error
    ? getGrowthApiErrorMessage(growthProgressQuery.error, '성장 정보를 불러오지 못했어요.')
    : null;
  const learningErrorMessage = learningQuizzesQuery.error
    ? getLearningApiErrorMessage(
        learningQuizzesQuery.error,
        '현재 티어 퀴즈를 불러오지 못했어요.',
      )
    : null;
  const quizCount = learningQuizzesQuery.data?.quizzes.length ?? 0;
  const segmentLabels = getLearningRecordSegments({
    reports: reportRecords.length,
    quizzes: quizCount,
    arenas: arenaRecords.length,
  });

  function handleQuizSubmit(conceptId: number) {
    const answerIndex = selectedAnswerByConceptId[conceptId];
    if (answerIndex == null) {
      setQuizErrorByConceptId((current) => ({
        ...current,
        [conceptId]: '보기를 하나 선택한 뒤 제출해 주세요.',
      }));
      return;
    }

    submitQuizMutation.mutate({
      concept_id: conceptId,
      answer_index: answerIndex,
    });
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={resetOnboarding} hitSlop={10} style={styles.headerBackButton}>
          <Text style={styles.headerBackButtonText}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>나의 학습 기록</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <GrowthProgressCard
          progress={growthProgressQuery.data ?? null}
          isLoading={Boolean(accessToken) && growthProgressQuery.isLoading}
          errorMessage={growthErrorMessage}
          requiresAuth={!accessToken}
          onPressPromotionTest={() => navigation.navigate('PromotionTest')}
        />

        <View style={styles.segmentControl}>
          {segmentLabels.map((segment) => {
            const selected = selectedSegment === segment.key;
            return (
              <Pressable
                key={segment.key}
                onPress={() => setSelectedSegment(segment.key)}
                style={[styles.segmentButton, selected && styles.segmentButtonSelected]}
              >
                <Text
                  style={[styles.segmentButtonText, selected && styles.segmentButtonTextSelected]}
                >
                  {segment.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.hintBanner}>
          <Text style={styles.hintIcon}>💡</Text>
          <Text style={styles.hintText}>{getLearningRecordHintMessage(selectedSegment)}</Text>
        </View>

        {selectedSegment === 'reports'
          ? reportRecords.map((record) => (
              <ReportCard
                key={record.id}
                mentor={record.mentor}
                date={record.date}
                title={record.title}
                summary={record.summary}
                understanding={understandingByRecordId[record.id] ?? record.understanding}
                onSelectUnderstanding={(next) =>
                  setUnderstandingByRecordId((current) => ({
                    ...current,
                    [record.id]: next,
                  }))
                }
              />
            ))
          : null}

        {selectedSegment === 'quizzes' && !accessToken ? (
          <InfoCard
            title="로그인하면 학습과 성장이 함께 기록돼요"
            description="현재 티어 퀴즈를 풀면 정답 시 성장 게이지가 함께 올라가요. 서버 계정으로 들어오면 이 연결 흐름을 바로 확인할 수 있어요."
          />
        ) : null}

        {selectedSegment === 'quizzes' && accessToken && learningQuizzesQuery.isLoading ? (
          <InfoCard
            title="현재 티어 퀴즈를 불러오는 중이에요"
            description="성장 단계와 맞는 학습 문항을 연결하고 있어요."
          />
        ) : null}

        {selectedSegment === 'quizzes' && accessToken && !learningQuizzesQuery.isLoading && learningErrorMessage ? (
          <InfoCard
            title="학습 퀴즈를 가져오지 못했어요"
            description={learningErrorMessage}
          />
        ) : null}

        {selectedSegment === 'quizzes' &&
        accessToken &&
        !learningQuizzesQuery.isLoading &&
        !learningErrorMessage &&
        learningQuizzesQuery.data?.quizzes.length === 0 ? (
          <InfoCard
            title="아직 연결된 퀴즈가 없어요"
            description="현재 티어에서 풀 수 있는 학습 퀴즈가 준비되면 여기에서 바로 이어서 볼 수 있어요."
          />
        ) : null}

        {selectedSegment === 'quizzes' && learningQuizzesQuery.data
          ? learningQuizzesQuery.data.quizzes.map((quiz) => {
              const isSubmitting =
                submitQuizMutation.isPending && submitQuizMutation.variables?.concept_id === quiz.concept_id;

              return (
                <QuizCard
                  key={quiz.concept_id}
                  quiz={quiz}
                  tierLabel={`${learningQuizzesQuery.data?.tier ?? 'T1'} 개념 퀴즈`}
                  expanded={expandedQuizConceptId === quiz.concept_id}
                  selectedAnswerIndex={selectedAnswerByConceptId[quiz.concept_id]}
                  submissionState={quizSubmissionByConceptId[quiz.concept_id]}
                  errorMessage={quizErrorByConceptId[quiz.concept_id]}
                  isSubmitting={isSubmitting}
                  onToggle={() =>
                    setExpandedQuizConceptId((current) =>
                      current === quiz.concept_id ? null : quiz.concept_id,
                    )
                  }
                  onSelectAnswer={(answerIndex) => {
                    setQuizErrorByConceptId((current) => ({
                      ...current,
                      [quiz.concept_id]: '',
                    }));
                    setSelectedAnswerByConceptId((current) => ({
                      ...current,
                      [quiz.concept_id]: answerIndex,
                    }));
                  }}
                  onSubmit={() => handleQuizSubmit(quiz.concept_id)}
                />
              );
            })
          : null}

        {selectedSegment === 'arenas'
          ? arenaRecords.map((record) => <ArenaCard key={record.id} {...record} />)
          : null}
      </ScrollView>

      <BottomNavMock />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 12,
    minHeight: 56,
    paddingHorizontal: 16,
  },
  headerBackButton: {
    alignItems: 'center',
    height: 24,
    justifyContent: 'center',
    width: 24,
  },
  headerBackButtonText: {
    color: colors.text,
    fontSize: 24,
    lineHeight: 24,
  },
  headerTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  scrollContent: {
    gap: 12,
    paddingBottom: 120,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  segmentControl: {
    backgroundColor: '#F4F5F4',
    borderRadius: 10,
    flexDirection: 'row',
    padding: 3,
  },
  segmentButton: {
    alignItems: 'center',
    borderRadius: 8,
    flex: 1,
    justifyContent: 'center',
    minHeight: 30,
  },
  segmentButtonSelected: {
    backgroundColor: colors.surface,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  segmentButtonText: {
    color: '#AFB4B0',
    fontSize: 13,
    fontWeight: '500',
  },
  segmentButtonTextSelected: {
    color: colors.primary,
    fontWeight: '700',
  },
  hintBanner: {
    alignItems: 'center',
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 10,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    minHeight: 40,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  hintIcon: {
    fontSize: 14,
  },
  hintText: {
    color: colors.text,
    flex: 1,
    fontSize: 12,
    fontWeight: '500',
    lineHeight: 16,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: 16,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'space-between',
  },
  cardDate: {
    color: '#AFB4B0',
    fontSize: 11,
  },
  reportMentor: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '500',
  },
  reportTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginTop: 4,
  },
  reportSummary: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  reportChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
  },
  reportChip: {
    borderRadius: 13,
    minHeight: 26,
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  reportChipIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
  },
  reportChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
    borderWidth: 1,
  },
  reportChipText: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '500',
  },
  reportChipTextSelected: {
    color: colors.surface,
    fontWeight: '700',
  },
  infoCard: {
    gap: 8,
  },
  infoTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  infoDescription: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  quizCard: {
    gap: 14,
    padding: 0,
  },
  quizCardExpanded: {
    paddingBottom: 16,
  },
  quizCardToggle: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 12,
    padding: 16,
  },
  quizIndicator: {
    alignItems: 'center',
    backgroundColor: colors.primarySoft,
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  quizIndicatorText: {
    fontSize: 18,
  },
  quizBody: {
    flex: 1,
    gap: 6,
  },
  quizMeta: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '500',
  },
  quizConcept: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '800',
  },
  quizQuestion: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 19,
  },
  quizResultChip: {
    alignSelf: 'flex-start',
    borderRadius: 11,
    marginTop: 4,
    minHeight: 22,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  quizResultChipCorrect: {
    backgroundColor: colors.primarySoft,
  },
  quizResultChipIncorrect: {
    backgroundColor: '#FCE7E3',
  },
  quizResultChipReview: {
    backgroundColor: colors.accentSoft,
  },
  quizResultChipText: {
    fontSize: 11,
    fontWeight: '700',
  },
  quizResultChipTextCorrect: {
    color: colors.primary,
  },
  quizResultChipTextIncorrect: {
    color: colors.rose,
  },
  quizResultChipTextReview: {
    color: '#8A6300',
  },
  quizArrow: {
    color: colors.muted,
    fontSize: 24,
    lineHeight: 24,
    marginTop: 20,
  },
  quizDetail: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
    gap: 12,
    paddingHorizontal: 16,
  },
  quizOptionList: {
    gap: 10,
    marginTop: 16,
  },
  quizOptionButton: {
    alignItems: 'flex-start',
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  quizOptionButtonIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  quizOptionButtonSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  quizOptionButtonPressed: {
    opacity: 0.88,
  },
  quizOptionIndex: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '800',
    lineHeight: 20,
    width: 16,
  },
  quizOptionIndexSelected: {
    color: colors.primary,
  },
  quizOptionText: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
  },
  quizOptionTextSelected: {
    color: colors.primary,
  },
  quizErrorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
  },
  quizExplanationBox: {
    backgroundColor: colors.background,
    borderRadius: 16,
    gap: 8,
    padding: 14,
  },
  quizExplanationTitle: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  quizExplanationText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  quizSyncText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 18,
  },
  quizSubmitButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 14,
    justifyContent: 'center',
    minHeight: 44,
  },
  quizSubmitButtonDisabled: {
    opacity: 0.4,
  },
  quizSubmitButtonPressed: {
    opacity: 0.9,
  },
  quizSubmitButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  arenaCard: {
    minHeight: 108,
    paddingRight: 36,
  },
  arenaAvatarRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 6,
    marginBottom: 8,
  },
  avatarColumn: {
    alignItems: 'center',
    gap: 6,
    width: 48,
  },
  avatarOuter: {
    alignItems: 'center',
    backgroundColor: colors.primarySoft,
    borderRadius: 24,
    height: 48,
    justifyContent: 'center',
    width: 48,
  },
  avatarInner: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 18,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  avatarLetter: {
    color: colors.primary,
    fontSize: 18,
    fontWeight: '700',
  },
  avatarLabel: {
    color: colors.muted,
    fontSize: 11,
  },
  arenaVs: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
    marginTop: 12,
  },
  arenaTopicLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '500',
    marginTop: 4,
  },
  arenaTopic: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginTop: 4,
  },
  bottomNav: {
    backgroundColor: colors.surface,
    bottom: 0,
    height: 82,
    left: 0,
    position: 'absolute',
    right: 0,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
  },
  bottomNavDivider: {
    backgroundColor: colors.border,
    height: 1,
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
  },
  bottomNavTabs: {
    flexDirection: 'row',
    paddingHorizontal: 0,
    paddingTop: 6,
  },
  bottomNavTab: {
    alignItems: 'center',
    flex: 1,
    gap: 8,
    height: 60,
    justifyContent: 'center',
  },
  bottomNavTabActive: {
    backgroundColor: colors.primarySoft,
    borderRadius: 18,
    marginHorizontal: 8,
  },
  bottomNavIcon: {
    fontSize: 22,
  },
  bottomNavLabel: {
    color: '#AFB4B0',
    fontSize: 11,
  },
  bottomNavLabelActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  homeIndicator: {
    alignSelf: 'center',
    backgroundColor: 'rgba(25, 28, 26, 0.15)',
    borderRadius: 2,
    height: 4,
    marginTop: 6,
    width: 134,
  },
});
