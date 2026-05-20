import { useState, type ReactNode } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
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
import { SelectionChip } from '../components/SelectionChip';
import {
  buildCompletedProfile,
  buildProfilePayload,
  buildRecommendedMentorsFromApi,
  EMPTY_ONBOARDING_SURVEY,
  getRecommendedMentors,
  isSurveyComplete,
  toggleInterest,
} from '../logic';
import type {
  MentorRecommendation,
  OnboardingSurvey,
  OnboardingSyncState,
} from '../types';

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.sectionCard}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <Text style={styles.sectionDescription}>{description}</Text>
      </View>
      <View style={styles.optionGrid}>{children}</View>
    </View>
  );
}

export function OnboardingScreen() {
  const accessToken = useUserStore((state) => state.accessToken);
  const finishOnboarding = useUserStore((state) => state.finishOnboarding);
  const [survey, setSurvey] = useState<OnboardingSurvey>(EMPTY_ONBOARDING_SURVEY);
  const [step, setStep] = useState<'survey' | 'mentor'>('survey');
  const [selectedMentorId, setSelectedMentorId] = useState<number | null>(null);
  const [remoteRecommendations, setRemoteRecommendations] = useState<MentorRecommendation[] | null>(
    null,
  );
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);

  const localRecommendations = getRecommendedMentors(survey);
  const recommendations = remoteRecommendations ?? localRecommendations;

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

  const surveyReady = isSurveyComplete(survey);
  const selectedMentor =
    recommendations.find((mentor) => mentor.id === selectedMentorId) ?? recommendations[0] ?? null;

  const helperText = accessToken
    ? '백엔드 온보딩 API와 연결된 상태입니다. 추천 결과는 서버 응답을 우선 사용하고, 실패하면 로컬 추천으로 이어집니다.'
    : '지금은 로그인 없는 로컬 모드예요. 설문과 멘토 선택 흐름만 먼저 확인할 수 있습니다.';

  async function handleShowMentors() {
    if (!surveyReady) {
      setSubmitMessage('질문에 모두 답하면 멘토 추천을 시작할 수 있어요.');
      return;
    }

    setSubmitMessage(null);
    setRemoteRecommendations(null);

    if (!accessToken) {
      setSelectedMentorId(localRecommendations[0]?.id ?? null);
      setStep('mentor');
      return;
    }

    try {
      const response = await recommendationMutation.mutateAsync(buildProfilePayload(survey));
      const nextRecommendations = buildRecommendedMentorsFromApi(response.recommended_mentors);
      setRemoteRecommendations(nextRecommendations);
      setSelectedMentorId(nextRecommendations[0]?.id ?? null);
      setStep('mentor');
      setSubmitMessage('서버 추천 결과를 기준으로 멘토 목록을 불러왔어요.');
    } catch {
      setSelectedMentorId(localRecommendations[0]?.id ?? null);
      setStep('mentor');
      setSubmitMessage('서버 추천을 불러오지 못해 로컬 추천으로 이어갑니다.');
    }
  }

  async function handleFinish() {
    if (!surveyReady || !selectedMentor) {
      return;
    }

    let syncState: OnboardingSyncState = 'local';
    setSubmitMessage(null);

    try {
      const result = await submitMutation.mutateAsync({
        currentSurvey: survey,
        mentorId: selectedMentor.id,
      });
      syncState = result.syncState;
      if (syncState === 'remote') {
        setSubmitMessage('서버 스펙에 맞춰 프로필과 멘토 선택까지 저장했어요.');
      }
    } catch {
      syncState = 'local';
      setSubmitMessage('현재 서버 연결이 불안정해서 로컬 완료 상태로 이어갑니다.');
    }

    finishOnboarding({
      profile: buildCompletedProfile(survey, selectedMentor.id, syncState),
      source: syncState,
    });
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>Mentors Onboarding</Text>
        <Text style={styles.heroTitle}>나한테 맞는 첫 멘토를 먼저 골라볼게요.</Text>
        <Text style={styles.heroDescription}>
          설문 응답을 바탕으로 투자 스타일에 맞는 멘토를 추천하고, 선택이 끝나면 T1부터
          바로 시작할 수 있게 연결해 둔 흐름입니다.
        </Text>
        <View style={styles.stepRow}>
          <View style={[styles.stepBadge, styles.stepBadgeActive]}>
            <Text style={[styles.stepBadgeText, styles.stepBadgeTextActive]}>1. 성향 설문</Text>
          </View>
          <View
            style={[
              styles.stepBadge,
              step === 'mentor' ? styles.stepBadgeActive : styles.stepBadgeIdle,
            ]}
          >
            <Text
              style={[
                styles.stepBadgeText,
                step === 'mentor' ? styles.stepBadgeTextActive : styles.stepBadgeTextIdle,
              ]}
            >
              2. 멘토 선택
            </Text>
          </View>
        </View>
      </View>

      <DevAccessTokenCard />

      {step === 'survey' ? (
        <>
          <Section title="현재 투자 경험" description="멘토가 설명 깊이를 조절하는 기준이 됩니다.">
            {experienceLevelOptions.map((option) => (
              <SelectionChip
                key={option.value}
                label={option.label}
                description={option.description}
                selected={survey.experienceLevel === option.value}
                onPress={() =>
                  setSurvey((current) => ({ ...current, experienceLevel: option.value }))
                }
              />
            ))}
          </Section>

          <Section title="관심 있는 주제" description="복수 선택이 가능합니다.">
            {interestOptions.map((option) => (
              <SelectionChip
                key={option.value}
                label={option.label}
                description={option.description}
                selected={survey.interests.includes(option.value)}
                onPress={() =>
                  setSurvey((current) => ({
                    ...current,
                    interests: toggleInterest(current.interests, option.value),
                  }))
                }
              />
            ))}
          </Section>

          <Section title="리스크 성향" description="어느 정도 변동성을 감수할지의 기준입니다.">
            {riskProfileOptions.map((option) => (
              <SelectionChip
                key={option.value}
                label={option.label}
                description={option.description}
                selected={survey.riskProfile === option.value}
                onPress={() => setSurvey((current) => ({ ...current, riskProfile: option.value }))}
              />
            ))}
          </Section>

          <Section title="이번 온보딩의 목표" description="첫 1주 동안 무엇을 배우고 싶은지 고릅니다.">
            {learningGoalOptions.map((option) => (
              <SelectionChip
                key={option.value}
                label={option.label}
                description={option.description}
                selected={survey.learningGoal === option.value}
                onPress={() =>
                  setSurvey((current) => ({ ...current, learningGoal: option.value }))
                }
              />
            ))}
          </Section>

          <Section title="원하는 코칭 스타일" description="멘토의 설명 톤과 템포를 맞춥니다.">
            {preferredStyleOptions.map((option) => (
              <SelectionChip
                key={option.value}
                label={option.label}
                description={option.description}
                selected={survey.preferredStyle === option.value}
                onPress={() =>
                  setSurvey((current) => ({ ...current, preferredStyle: option.value }))
                }
              />
            ))}
          </Section>

          <View style={styles.footerCard}>
            <Text style={styles.helperText}>{helperText}</Text>
            <Pressable
              onPress={handleShowMentors}
              style={[
                styles.primaryButton,
                (!surveyReady || recommendationMutation.isPending) && styles.primaryButtonDisabled,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                {recommendationMutation.isPending ? '추천 불러오는 중...' : '추천 멘토 보기'}
              </Text>
            </Pressable>
            {submitMessage ? <Text style={styles.noticeText}>{submitMessage}</Text> : null}
          </View>
        </>
      ) : (
        <>
          <View style={styles.sectionCard}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>추천 멘토</Text>
              <Text style={styles.sectionDescription}>
                로그인 상태라면 백엔드 추천 결과를 그대로 사용하고, 아니면 프론트 fallback
                추천을 보여줍니다.
              </Text>
            </View>
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
          </View>

          <View style={styles.footerCard}>
            <Text style={styles.helperText}>{helperText}</Text>
            {submitMutation.isPending ? (
              <View style={styles.pendingRow}>
                <ActivityIndicator color={colors.primary} />
                <Text style={styles.pendingText}>멘토 선택 내용을 저장하고 있어요.</Text>
              </View>
            ) : null}
            <View style={styles.actionRow}>
              <Pressable
                onPress={() => {
                  setRemoteRecommendations(null);
                  setStep('survey');
                }}
                style={[styles.secondaryButton, styles.actionButton]}
              >
                <Text style={styles.secondaryButtonText}>응답 수정</Text>
              </Pressable>
              <Pressable onPress={handleFinish} style={[styles.primaryButton, styles.actionButton]}>
                <Text style={styles.primaryButtonText}>이 멘토로 시작하기</Text>
              </Pressable>
            </View>
            {submitMessage ? <Text style={styles.noticeText}>{submitMessage}</Text> : null}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 16,
    backgroundColor: colors.background,
  },
  heroCard: {
    borderRadius: 28,
    backgroundColor: colors.text,
    padding: 22,
    gap: 12,
  },
  eyebrow: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  heroTitle: {
    color: colors.surface,
    fontSize: 30,
    fontWeight: '800',
    lineHeight: 36,
  },
  heroDescription: {
    color: '#D9DEE7',
    fontSize: 15,
    lineHeight: 22,
  },
  stepRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  stepBadge: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  stepBadgeActive: {
    backgroundColor: colors.accent,
  },
  stepBadgeIdle: {
    backgroundColor: '#2D3747',
  },
  stepBadgeText: {
    fontSize: 12,
    fontWeight: '800',
  },
  stepBadgeTextActive: {
    color: colors.text,
  },
  stepBadgeTextIdle: {
    color: colors.surface,
  },
  sectionCard: {
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: 18,
    gap: 16,
  },
  sectionHeader: {
    gap: 6,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '800',
  },
  sectionDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  optionGrid: {
    gap: 12,
  },
  mentorList: {
    gap: 12,
  },
  footerCard: {
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 18,
    gap: 14,
  },
  helperText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  actionButton: {
    flex: 1,
  },
  primaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 18,
    backgroundColor: colors.primary,
    minHeight: 54,
    paddingHorizontal: 16,
  },
  primaryButtonDisabled: {
    opacity: 0.45,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 15,
    fontWeight: '800',
  },
  secondaryButton: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 18,
    backgroundColor: colors.accentSoft,
    minHeight: 54,
    paddingHorizontal: 16,
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  noticeText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 19,
  },
  pendingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  pendingText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
});
