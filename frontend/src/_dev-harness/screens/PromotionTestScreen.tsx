import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import type { RootStackParamList } from '../navigation/types';
import {
  getGrowthApiErrorMessage,
  getGrowthProgress,
  submitPromotionTest,
} from '@/features/growth/api';
import type { PromotionTestQuestion, PromotionTestResponse } from '@/features/growth/types';
import {
  buildPromotionTestPayload,
  getPromotionResultHeadline,
  getUnlockLabel,
  isPromotionTestComplete,
} from '../growth/logic';

type PromotionTestScreenProps = NativeStackScreenProps<RootStackParamList, 'PromotionTest'>;

function ResultCard({
  result,
  onPressPrimary,
  onPressSecondary,
}: {
  result: PromotionTestResponse;
  onPressPrimary: () => void;
  onPressSecondary: (() => void) | null;
}) {
  return (
    <View style={styles.resultCard}>
      <Text style={styles.resultEyebrow}>{result.passed ? 'Promotion Passed' : 'Retry Ready'}</Text>
      <Text style={styles.resultTitle}>{getPromotionResultHeadline(result)}</Text>
      <Text style={styles.resultDescription}>
        {result.correct_answers}/{result.total_questions}문항 정답, 최종 점수 {result.score_percent}
        점
      </Text>
      <Text style={styles.resultMessage}>{result.message}</Text>
      {result.unlocked_features.length > 0 ? (
        <View style={styles.featureRow}>
          {result.unlocked_features.map((feature) => (
            <View key={feature} style={styles.featureChip}>
              <Text style={styles.featureChipText}>{getUnlockLabel(feature)}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <Pressable onPress={onPressPrimary} style={styles.primaryButton}>
        <Text style={styles.primaryButtonText}>
          {result.passed ? '홈으로 돌아가기' : '다시 확인하기'}
        </Text>
      </Pressable>
      {onPressSecondary ? (
        <Pressable onPress={onPressSecondary} style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>답안 다시 고르기</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function QuestionCard({
  question,
  selectedChoiceId,
  onSelect,
}: {
  question: PromotionTestQuestion;
  selectedChoiceId: string | undefined;
  onSelect: (choiceId: string) => void;
}) {
  return (
    <View style={styles.questionCard}>
      <Text style={styles.questionNumber}>{question.question_id.toUpperCase()}</Text>
      <Text style={styles.questionPrompt}>{question.prompt}</Text>
      <View style={styles.choiceList}>
        {question.choices.map((choice) => {
          const selected = selectedChoiceId === choice.choice_id;
          return (
            <Pressable
              key={choice.choice_id}
              onPress={() => onSelect(choice.choice_id)}
              style={({ pressed }) => [
                styles.choiceButton,
                selected ? styles.choiceButtonSelected : styles.choiceButtonIdle,
                pressed && styles.choiceButtonPressed,
              ]}
            >
              <Text style={[styles.choiceLabel, selected && styles.choiceLabelSelected]}>
                {choice.choice_id}. {choice.text}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function PromotionTestScreen({ navigation }: PromotionTestScreenProps) {
  const accessToken = useUserStore((state) => state.accessToken);
  const queryClient = useQueryClient();
  const [answersByQuestionId, setAnswersByQuestionId] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [latestResult, setLatestResult] = useState<PromotionTestResponse | null>(null);
  const queryKey = ['growth-progress', accessToken];
  const progressQuery = useQuery({
    queryKey,
    queryFn: getGrowthProgress,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const submitMutation = useMutation({
    mutationFn: submitPromotionTest,
    onSuccess: async (result) => {
      setLatestResult(result);
      setSubmitError(null);
      await queryClient.invalidateQueries({ queryKey });
    },
    onError: (error) => {
      setLatestResult(null);
      setSubmitError(getGrowthApiErrorMessage(error, '승급시험 제출에 실패했어요.'));
    },
  });

  const preview = progressQuery.data?.promotion_test ?? null;
  const questions = preview?.questions ?? [];
  const readyToSubmit = isPromotionTestComplete(questions, answersByQuestionId);

  function handleChoiceSelect(questionId: string, choiceId: string) {
    setSubmitError(null);
    setAnswersByQuestionId((current) => ({
      ...current,
      [questionId]: choiceId,
    }));
  }

  function handleSubmit() {
    if (!preview) {
      setSubmitError('아직 응시 가능한 승급시험이 없어요.');
      return;
    }

    if (!readyToSubmit) {
      setSubmitError('모든 문항에 답한 뒤 제출해 주세요.');
      return;
    }

    submitMutation.mutate(buildPromotionTestPayload(preview.questions, answersByQuestionId));
  }

  function resetResult() {
    setLatestResult(null);
    setSubmitError(null);
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>Promotion Test</Text>
        <Text style={styles.heroTitle}>승급시험</Text>
        <Text style={styles.heroDescription}>
          이해도 게이지가 80%를 넘으면 현재 티어에서 다음 티어로 넘어가는 시험에 응시할 수 있어요.
        </Text>
      </View>

      {!accessToken ? (
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>로그인 후 승급시험을 진행할 수 있어요</Text>
          <Text style={styles.infoDescription}>
            현재 앱은 로컬 온보딩도 지원하지만, 성장 데이터와 시험 결과는 서버 계정과 함께
            저장됩니다.
          </Text>
        </View>
      ) : null}

      {accessToken && progressQuery.isLoading ? (
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>시험 정보를 불러오는 중이에요</Text>
          <Text style={styles.infoDescription}>
            현재 응시 가능한 시험과 문항 구성을 확인하고 있어요.
          </Text>
        </View>
      ) : null}

      {accessToken && !progressQuery.isLoading && progressQuery.error ? (
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>시험 정보를 가져오지 못했어요</Text>
          <Text style={styles.infoDescription}>
            {getGrowthApiErrorMessage(progressQuery.error, '잠시 후 다시 시도해 주세요.')}
          </Text>
        </View>
      ) : null}

      {latestResult ? (
        <ResultCard
          result={latestResult}
          onPressPrimary={() => {
            if (latestResult.passed) {
              navigation.goBack();
              return;
            }

            resetResult();
          }}
          onPressSecondary={latestResult.passed ? null : resetResult}
        />
      ) : null}

      {accessToken && !progressQuery.isLoading && !progressQuery.error && !preview ? (
        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>아직 응시 가능한 승급시험이 없어요</Text>
          <Text style={styles.infoDescription}>
            홈 화면의 성장 카드에서 이해도 게이지를 확인하고, 80% 이상이 되면 다시 들어와 주세요.
          </Text>
        </View>
      ) : null}

      {preview ? (
        <View style={styles.paperCard}>
          <View style={styles.summaryRow}>
            <View style={styles.summaryPill}>
              <Text style={styles.summaryLabel}>목표 티어</Text>
              <Text style={styles.summaryValue}>{preview.target_tier}</Text>
            </View>
            <View style={styles.summaryPill}>
              <Text style={styles.summaryLabel}>합격 기준</Text>
              <Text style={styles.summaryValue}>{preview.passing_score}점</Text>
            </View>
            <View style={styles.summaryPill}>
              <Text style={styles.summaryLabel}>문항 수</Text>
              <Text style={styles.summaryValue}>{preview.question_count}개</Text>
            </View>
          </View>

          {questions.map((question) => (
            <QuestionCard
              key={question.question_id}
              question={question}
              selectedChoiceId={answersByQuestionId[question.question_id]}
              onSelect={(choiceId) => handleChoiceSelect(question.question_id, choiceId)}
            />
          ))}

          {submitError ? <Text style={styles.errorText}>{submitError}</Text> : null}

          <Pressable
            onPress={handleSubmit}
            disabled={submitMutation.isPending}
            style={({ pressed }) => [
              styles.submitButton,
              (!readyToSubmit || submitMutation.isPending) && styles.submitButtonDisabled,
              pressed && readyToSubmit && !submitMutation.isPending && styles.submitButtonPressed,
            ]}
          >
            <Text style={styles.submitButtonText}>
              {submitMutation.isPending ? '채점 중...' : '답안 제출하기'}
            </Text>
          </Pressable>
        </View>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    backgroundColor: colors.background,
    gap: 16,
  },
  heroCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 10,
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  heroTitle: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '800',
  },
  heroDescription: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 10,
  },
  infoTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  infoDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  paperCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 16,
  },
  summaryRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  summaryPill: {
    minWidth: 92,
    backgroundColor: colors.primarySoft,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 4,
  },
  summaryLabel: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  summaryValue: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  questionCard: {
    backgroundColor: colors.background,
    borderRadius: 20,
    padding: 16,
    gap: 12,
  },
  questionNumber: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.8,
  },
  questionPrompt: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '700',
    lineHeight: 24,
  },
  choiceList: {
    gap: 10,
  },
  choiceButton: {
    borderRadius: 16,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 14,
  },
  choiceButtonIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  choiceButtonSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  choiceButtonPressed: {
    opacity: 0.88,
  },
  choiceLabel: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
  },
  choiceLabelSelected: {
    color: colors.primary,
  },
  errorText: {
    color: colors.rose,
    fontSize: 14,
    lineHeight: 20,
  },
  submitButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 18,
    paddingHorizontal: 18,
    paddingVertical: 16,
  },
  submitButtonDisabled: {
    opacity: 0.45,
  },
  submitButtonPressed: {
    opacity: 0.9,
  },
  submitButtonText: {
    color: colors.surface,
    fontSize: 15,
    fontWeight: '700',
  },
  resultCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 12,
  },
  resultEyebrow: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  resultTitle: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '800',
  },
  resultDescription: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '600',
  },
  resultMessage: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  featureRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  featureChip: {
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  featureChipText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  secondaryButton: {
    alignItems: 'center',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
});
