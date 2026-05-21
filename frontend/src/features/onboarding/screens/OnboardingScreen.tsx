import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { DevAccessTokenCard } from '@/components/DevAccessTokenCard';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { saveMentorSelection, saveOnboardingProfile } from '../api';
import {
  experienceLevelOptions,
  interestOptions,
  learningGoalOptions,
  preferredStyleOptions,
  riskProfileOptions,
} from '../data';
import { MentorRecommendationCard } from '../components/MentorRecommendationCard';
import {
  buildCompletedProfile,
  buildProfilePayload,
  buildRecommendedMentorsFromApi,
  EMPTY_ONBOARDING_SURVEY,
  getOnboardingProgressValue,
  getOnboardingStepLabel,
  getRecommendedMentors,
  isSurveyComplete,
  ONBOARDING_STEP_COUNT,
  toggleInterest,
} from '../logic';
import type {
  MentorRecommendation,
  OnboardingSurvey,
  OnboardingSyncState,
  SelectOption,
} from '../types';

type AgeRange = 'teens' | 'early20s' | 'late20s' | 'thirties' | 'fortiesPlus';
type SurveyStepKey = 'age' | 'experience' | 'risk' | 'goal' | 'style' | 'interests';

interface AgeOption {
  value: AgeRange;
  label: string;
}

const ageOptions: AgeOption[] = [
  { value: 'teens', label: '10대' },
  { value: 'early20s', label: '20대 초반 (20~24세)' },
  { value: 'late20s', label: '20대 후반 (25~29세)' },
  { value: 'thirties', label: '30대' },
  { value: 'fortiesPlus', label: '40대 이상' },
];

const surveySteps: {
  key: SurveyStepKey;
  title: string;
  subtitle: string;
  helper?: string;
}[] = [
  {
    key: 'age',
    title: '연령대가\n어떻게 되시나요?',
    subtitle: '안녕하세요, 투자자님!',
  },
  {
    key: 'experience',
    title: '투자 경험이\n있으신가요?',
    subtitle: '답변에 맞춰 멘토의 설명 깊이를 조절할게요.',
  },
  {
    key: 'risk',
    title: '어느 정도의 리스크가\n편하신가요?',
    subtitle: '시장 변동을 대하는 톤을 맞추기 위한 질문이에요.',
  },
  {
    key: 'goal',
    title: '이번 온보딩에서\n가장 얻고 싶은 것은?',
    subtitle: '첫 주 학습 루틴과 콘텐츠 흐름을 여기에 맞춰 드릴게요.',
  },
  {
    key: 'style',
    title: '어떤 방식의 설명이\n편하신가요?',
    subtitle: '멘토의 말투와 템포를 이 선호에 맞춰 볼게요.',
  },
  {
    key: 'interests',
    title: '관심 있는 투자 주제를\n골라주세요',
    subtitle: '마지막 질문이에요.',
    helper: '관심사는 여러 개 선택할 수 있어요.',
  },
];

function OptionRow({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.optionRow,
        selected && styles.optionRowSelected,
        pressed && styles.pressed,
      ]}
    >
      <View style={[styles.radioOuter, selected && styles.radioOuterSelected]}>
        {selected ? <View style={styles.radioInner} /> : null}
      </View>
      <Text style={[styles.optionLabel, selected && styles.optionLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

function InterestChip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.interestChip,
        selected && styles.interestChipSelected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.interestChipLabel, selected && styles.interestChipLabelSelected]}>
        {label}
      </Text>
    </Pressable>
  );
}

function getSingleSelectOptions(stepKey: SurveyStepKey): AgeOption[] | SelectOption<string>[] {
  switch (stepKey) {
    case 'age':
      return ageOptions;
    case 'experience':
      return experienceLevelOptions;
    case 'risk':
      return riskProfileOptions;
    case 'goal':
      return learningGoalOptions;
    case 'style':
      return preferredStyleOptions;
    default:
      return [];
  }
}

export function OnboardingScreen() {
  const accessToken = useUserStore((state) => state.accessToken);
  const finishOnboarding = useUserStore((state) => state.finishOnboarding);
  const [ageRange, setAgeRange] = useState<AgeRange | null>(null);
  const [survey, setSurvey] = useState<OnboardingSurvey>(EMPTY_ONBOARDING_SURVEY);
  const [mode, setMode] = useState<'survey' | 'mentor'>('survey');
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [selectedMentorId, setSelectedMentorId] = useState<number | null>(null);
  const [remoteRecommendations, setRemoteRecommendations] = useState<MentorRecommendation[] | null>(
    null,
  );
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const localRecommendations = getRecommendedMentors(survey);
  const recommendations = remoteRecommendations ?? localRecommendations;
  const currentStep = surveySteps[currentStepIndex];
  const isMentorStep = mode === 'mentor';
  const surveyReady = isSurveyComplete(survey);
  const selectedMentor =
    recommendations.find((mentor) => mentor.id === selectedMentorId) ?? recommendations[0] ?? null;

  const recommendationMutation = useMutation({
    mutationFn: saveOnboardingProfile,
  });

  const submitMutation = useMutation({
    mutationFn: async ({
      currentSurvey,
      mentorId,
    }: {
      currentSurvey: OnboardingSurvey;
      mentorId: number;
    }) => {
      if (!accessToken) {
        return { syncState: 'local' as const };
      }

      await saveOnboardingProfile(buildProfilePayload(currentSurvey));
      await saveMentorSelection({ mentor_id: mentorId });

      return { syncState: 'remote' as const };
    },
  });

  function isCurrentStepComplete(): boolean {
    switch (currentStep.key) {
      case 'age':
        return Boolean(ageRange);
      case 'experience':
        return Boolean(survey.experienceLevel);
      case 'risk':
        return Boolean(survey.riskProfile);
      case 'goal':
        return Boolean(survey.learningGoal);
      case 'style':
        return Boolean(survey.preferredStyle);
      case 'interests':
        return survey.interests.length > 0;
      default:
        return false;
    }
  }

  function getSelectedSingleValue(): string | null {
    switch (currentStep.key) {
      case 'age':
        return ageRange;
      case 'experience':
        return survey.experienceLevel;
      case 'risk':
        return survey.riskProfile;
      case 'goal':
        return survey.learningGoal;
      case 'style':
        return survey.preferredStyle;
      default:
        return null;
    }
  }

  function handleSingleSelect(value: string) {
    switch (currentStep.key) {
      case 'age':
        setAgeRange(value as AgeRange);
        return;
      case 'experience':
        setSurvey((current) => ({
          ...current,
          experienceLevel: value as OnboardingSurvey['experienceLevel'],
        }));
        return;
      case 'risk':
        setSurvey((current) => ({
          ...current,
          riskProfile: value as OnboardingSurvey['riskProfile'],
        }));
        return;
      case 'goal':
        setSurvey((current) => ({
          ...current,
          learningGoal: value as OnboardingSurvey['learningGoal'],
        }));
        return;
      case 'style':
        setSurvey((current) => ({
          ...current,
          preferredStyle: value as OnboardingSurvey['preferredStyle'],
        }));
        return;
      default:
        return;
    }
  }

  async function handleShowMentors() {
    if (!surveyReady) {
      return;
    }

    setSubmitMessage(null);
    setRemoteRecommendations(null);

    if (!accessToken) {
      setSelectedMentorId(localRecommendations[0]?.id ?? null);
      setMode('mentor');
      return;
    }

    try {
      const response = await recommendationMutation.mutateAsync(buildProfilePayload(survey));
      const nextRecommendations = buildRecommendedMentorsFromApi(response.recommended_mentors);
      const fallbackRecommendations =
        nextRecommendations.length > 0 ? nextRecommendations : localRecommendations;

      setRemoteRecommendations(nextRecommendations.length > 0 ? nextRecommendations : null);
      setSelectedMentorId(fallbackRecommendations[0]?.id ?? null);
      setMode('mentor');
    } catch {
      setSelectedMentorId(localRecommendations[0]?.id ?? null);
      setMode('mentor');
      setSubmitMessage('서버 추천을 불러오지 못해 로컬 추천 결과로 이어서 보여드릴게요.');
    }
  }

  async function handleFinish() {
    if (!surveyReady || !selectedMentor) {
      return;
    }

    let syncState: OnboardingSyncState = 'local';

    try {
      const result = await submitMutation.mutateAsync({
        currentSurvey: survey,
        mentorId: selectedMentor.id,
      });
      syncState = result.syncState;
    } catch {
      syncState = 'local';
    }

    finishOnboarding({
      profile: buildCompletedProfile(survey, selectedMentor.id, syncState),
      source: syncState,
    });
  }

  function handleBack() {
    if (isMentorStep) {
      setMode('survey');
      return;
    }

    setSubmitMessage(null);
    setCurrentStepIndex((current) => Math.max(0, current - 1));
  }

  function handlePrimaryAction() {
    if (!isCurrentStepComplete()) {
      return;
    }

    if (currentStepIndex === surveySteps.length - 1) {
      void handleShowMentors();
      return;
    }

    setCurrentStepIndex((current) => Math.min(current + 1, surveySteps.length - 1));
  }

  const helperText = accessToken
    ? '서버 추천 결과를 우선 보여드리고, 선택을 완료하면 실제 온보딩 API에도 저장해요.'
    : '지금은 로컬 미리보기 모드예요. 설문 흐름과 멘토 추천만 먼저 확인할 수 있어요.';

  const primaryButtonLabel =
    currentStepIndex === surveySteps.length - 1 ? '추천 멘토 보기' : '다음';

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          {isMentorStep || currentStepIndex > 0 ? (
            <Pressable onPress={handleBack} hitSlop={10} style={styles.backButton}>
              <Text style={styles.backButtonText}>←</Text>
            </Pressable>
          ) : (
            <View style={styles.backButtonPlaceholder} />
          )}
          <Text style={styles.headerStepText}>
            {isMentorStep
              ? '멘토 선택'
              : getOnboardingStepLabel(currentStepIndex, ONBOARDING_STEP_COUNT)}
          </Text>
        </View>
        {!isMentorStep ? (
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                {
                  width: `${getOnboardingProgressValue(currentStepIndex, ONBOARDING_STEP_COUNT) * 100}%`,
                },
              ]}
            />
          </View>
        ) : null}
      </View>

      <View style={styles.sheet}>
        {isMentorStep ? (
          <>
            <ScrollView
              contentContainerStyle={styles.scrollContent}
              showsVerticalScrollIndicator={false}
            >
              <Text style={styles.subtitle}>답변을 바탕으로 준비했어요</Text>
              <Text style={styles.title}>같이 시작할 멘토를 골라볼까요?</Text>
              <Text style={styles.helperText}>{helperText}</Text>

              {submitMessage ? (
                <View style={styles.noticeBanner}>
                  <Text style={styles.noticeBannerText}>{submitMessage}</Text>
                </View>
              ) : null}

              {recommendationMutation.isPending ? (
                <View style={styles.loadingRow}>
                  <ActivityIndicator color={colors.primary} />
                  <Text style={styles.loadingText}>추천 멘토를 불러오는 중이에요.</Text>
                </View>
              ) : null}

              <View style={styles.mentorList}>
                {recommendations.map((mentor) => (
                  <MentorRecommendationCard
                    key={mentor.id}
                    mentor={mentor}
                    selected={selectedMentor?.id === mentor.id}
                    onPress={() => setSelectedMentorId(mentor.id)}
                  />
                ))}
              </View>

              <DevAccessTokenCard />
            </ScrollView>

            <View style={styles.footerRow}>
              <Pressable onPress={handleBack} style={[styles.secondaryButton, styles.footerAction]}>
                <Text style={styles.secondaryButtonText}>응답 수정</Text>
              </Pressable>
              <Pressable
                onPress={() => {
                  void handleFinish();
                }}
                style={[
                  styles.primaryButton,
                  styles.footerAction,
                  (submitMutation.isPending || !selectedMentor) && styles.buttonDisabled,
                ]}
              >
                <Text style={styles.primaryButtonText}>
                  {submitMutation.isPending ? '저장 중...' : '이 멘토로 시작하기'}
                </Text>
              </Pressable>
            </View>
          </>
        ) : (
          <>
            <ScrollView
              contentContainerStyle={styles.scrollContent}
              showsVerticalScrollIndicator={false}
            >
              <Text style={styles.subtitle}>{currentStep.subtitle}</Text>
              <Text style={styles.title}>{currentStep.title}</Text>
              {currentStep.helper ? (
                <Text style={styles.helperText}>{currentStep.helper}</Text>
              ) : null}

              {currentStep.key === 'interests' ? (
                <View style={styles.interestWrap}>
                  {interestOptions.map((option) => (
                    <InterestChip
                      key={option.value}
                      label={option.label}
                      selected={survey.interests.includes(option.value)}
                      onPress={() =>
                        setSurvey((current) => ({
                          ...current,
                          interests: toggleInterest(current.interests, option.value),
                        }))
                      }
                    />
                  ))}
                </View>
              ) : (
                <View style={styles.optionList}>
                  {getSingleSelectOptions(currentStep.key).map((option) => (
                    <OptionRow
                      key={option.value}
                      label={option.label}
                      selected={getSelectedSingleValue() === option.value}
                      onPress={() => handleSingleSelect(option.value)}
                    />
                  ))}
                </View>
              )}
            </ScrollView>

            <View style={styles.footer}>
              <Pressable
                onPress={handlePrimaryAction}
                style={[
                  styles.primaryButton,
                  (!isCurrentStepComplete() || recommendationMutation.isPending) &&
                    styles.buttonDisabled,
                ]}
              >
                <Text style={styles.primaryButtonText}>
                  {recommendationMutation.isPending
                    ? '추천 멘토 불러오는 중...'
                    : primaryButtonLabel}
                </Text>
              </Pressable>
            </View>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.primary,
  },
  header: {
    backgroundColor: colors.primary,
    paddingHorizontal: 24,
    paddingTop: 8,
    paddingBottom: 16,
  },
  headerTopRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 40,
  },
  backButton: {
    alignItems: 'center',
    height: 32,
    justifyContent: 'center',
    width: 32,
  },
  backButtonPlaceholder: {
    height: 32,
    width: 32,
  },
  backButtonText: {
    color: colors.surface,
    fontSize: 24,
    lineHeight: 24,
  },
  headerStepText: {
    color: '#CCF2DE',
    fontSize: 12,
    fontWeight: '600',
  },
  progressTrack: {
    backgroundColor: 'rgba(255,255,255,0.32)',
    borderRadius: 999,
    height: 4,
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: {
    backgroundColor: colors.surface,
    borderRadius: 999,
    height: '100%',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    flex: 1,
    marginTop: -8,
    overflow: 'hidden',
  },
  scrollContent: {
    gap: 20,
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 28,
  },
  subtitle: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '700',
    lineHeight: 32,
  },
  helperText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  optionList: {
    gap: 10,
    marginTop: 12,
  },
  optionRow: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    minHeight: 48,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  optionRowSelected: {
    borderColor: colors.primary,
  },
  radioOuter: {
    alignItems: 'center',
    backgroundColor: '#E9ECE8',
    borderRadius: 999,
    height: 20,
    justifyContent: 'center',
    width: 20,
  },
  radioOuterSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderWidth: 1,
  },
  radioInner: {
    backgroundColor: colors.primary,
    borderRadius: 999,
    height: 8,
    width: 8,
  },
  optionLabel: {
    color: colors.text,
    flex: 1,
    fontSize: 15,
    lineHeight: 22,
  },
  optionLabelSelected: {
    fontWeight: '600',
  },
  interestWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginTop: 12,
  },
  interestChip: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  interestChipSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  interestChipLabel: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '500',
  },
  interestChipLabelSelected: {
    color: colors.surface,
  },
  mentorList: {
    gap: 12,
    marginTop: 4,
  },
  noticeBanner: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  noticeBannerText: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 19,
  },
  loadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  loadingText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '500',
  },
  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: 24,
    paddingBottom: 16,
    paddingTop: 8,
  },
  footerRow: {
    backgroundColor: colors.surface,
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 24,
    paddingBottom: 16,
    paddingTop: 8,
  },
  footerAction: {
    flex: 1,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 14,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 20,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '600',
  },
  pressed: {
    opacity: 0.9,
  },
});
