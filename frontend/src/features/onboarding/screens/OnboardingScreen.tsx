import { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  ScrollView,
  ActivityIndicator,
  TextInput,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { saveOnboardingProfile, saveMentorSelection, getOnboardingStatus } from '../api';
import { shouldUseLocalOnboardingFallback } from '../flow';
import type { MentorRecommendation, OnboardingSurvey, OnboardingSyncState } from '../types';
import {
  ageOptions,
  experienceOptions,
  goalOptions,
  scaleOptions,
  riskOptions,
  simpleInterestOptions,
  mapGoalToBackend,
} from '../data/surveyData';

// Reusable Local Mentor Recommendation Card Component to align with AGENTS.md rules
interface MentorCardProps {
  mentor: MentorRecommendation;
  selected: boolean;
  onPress: () => void;
}

function LocalMentorCard({ mentor, selected, onPress }: MentorCardProps) {
  const accentColor = mentor.accentColor || colors.primary;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        cardStyles.container,
        {
          borderColor: selected ? accentColor : colors.border,
          backgroundColor: selected ? `${accentColor}10` : colors.surface,
        },
        pressed && cardStyles.pressed,
      ]}
    >
      <View style={cardStyles.headerRow}>
        <View style={cardStyles.headerText}>
          <Text style={cardStyles.name}>{mentor.name}</Text>
          <Text style={[cardStyles.title, { color: accentColor }]}>{mentor.title}</Text>
        </View>
        <View style={[cardStyles.scoreBadge, { backgroundColor: `${accentColor}18` }]}>
          <Text style={[cardStyles.scoreText, { color: accentColor }]}>
            추천도 {mentor.score || 3}
          </Text>
        </View>
      </View>

      <Text style={cardStyles.oneLiner}>{mentor.oneLiner}</Text>
      <Text style={cardStyles.idealFor}>어울리는 사용자: {mentor.idealFor}</Text>

      <View style={cardStyles.reasonList}>
        {mentor.reasons.map((reason) => (
          <Text key={reason} style={cardStyles.reasonItem}>
            • {reason}
          </Text>
        ))}
      </View>

      <View style={cardStyles.tagRow}>
        {(mentor.strengths || []).map((strength) => (
          <View key={strength} style={cardStyles.tag}>
            <Text style={cardStyles.tagText}>{strength}</Text>
          </View>
        ))}
      </View>
    </Pressable>
  );
}

const cardStyles = StyleSheet.create({
  container: {
    borderRadius: 24,
    borderWidth: 1,
    padding: 20,
    gap: 12,
  },
  pressed: {
    opacity: 0.9,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  headerText: {
    flex: 1,
    gap: 4,
  },
  name: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  title: {
    fontSize: 15,
    fontWeight: '700',
  },
  scoreBadge: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  scoreText: {
    fontSize: 12,
    fontWeight: '800',
  },
  oneLiner: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  idealFor: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  reasonList: {
    gap: 6,
  },
  reasonItem: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: colors.surface,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  tagText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
});

export function OnboardingScreen() {
  const queryClient = useQueryClient();
  const accessToken = useUserStore((state) => state.accessToken);
  const finishOnboarding = useUserStore((state) => state.finishOnboarding);

  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<'survey' | 'mentor'>('survey');

  // Survey States
  const [selectedAge, setSelectedAge] = useState<string | null>(null);
  const [selectedExperience, setSelectedExperience] = useState<string | null>(null);
  const [selectedGoals, setSelectedGoals] = useState<string[]>([]);
  const [selectedScale, setSelectedScale] = useState<string | null>(null);
  const [selectedRisk, setSelectedRisk] = useState<string | null>(null);
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);

  // Results State
  const [recommendedMentors, setRecommendedMentors] = useState<MentorRecommendation[]>([]);
  const [selectedMentorId, setSelectedMentorId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const profileMutation = useMutation({
    mutationFn: saveOnboardingProfile,
  });

  const mentorMutation = useMutation({
    mutationFn: saveMentorSelection,
  });

  function isStepValid(): boolean {
    switch (step) {
      case 1:
        return selectedAge !== null;
      case 2:
        return selectedExperience !== null;
      case 3:
        return selectedGoals.length > 0;
      case 4:
        return selectedScale !== null;
      case 5:
        return selectedRisk !== null;
      case 6:
        return selectedInterests.length > 0;
      default:
        return false;
    }
  }

  function handleGoalToggle(val: string) {
    if (selectedGoals.includes(val)) {
      setSelectedGoals(selectedGoals.filter((g) => g !== val));
    } else {
      setSelectedGoals([...selectedGoals, val]);
    }
  }

  function toggleChildInterest(interest: string) {
    if (selectedInterests.includes(interest)) {
      setSelectedInterests(selectedInterests.filter((x) => x !== interest));
    } else {
      setSelectedInterests([...selectedInterests, interest]);
    }
  }

  async function handleNextStep() {
    if (!isStepValid()) return;
    setSubmitError(null);

    if (step < 6) {
      setStep(step + 1);
    } else {
      // Build profile payload and request recommendations
      await submitSurveyProfile();
    }
  }

  function handleBack() {
    if (mode === 'mentor') {
      setMode('survey');
      return;
    }
    if (step > 1) {
      setStep(step - 1);
    }
  }

  async function submitSurveyProfile() {
    setSubmitError(null);
    // Map goals to one of the backend tags
    const mappedGoal = mapGoalToBackend(selectedGoals);

    // simpleInterestOptions already map directly to valid InterestTag values
    const interestsPayload = selectedInterests;

    // Build the Survey answers logging list
    const answersPayload = [
      {
        question_code: 'age_group',
        question_text: '연령대',
        answer_value: ageOptions.find((o) => o.value === selectedAge)?.label || selectedAge || '',
      },
      {
        question_code: 'experience_level',
        question_text: '투자 경험',
        answer_value: experienceOptions.find((o) => o.value === selectedExperience)?.label || '',
      },
      {
        question_code: 'interest_reason',
        question_text: '투자 관심 이유',
        answer_value: selectedGoals
          .map((g) => goalOptions.find((o) => o.value === g)?.label || '')
          .join(', '),
      },
      {
        question_code: 'investment_scale',
        question_text: '투자 자산 규모',
        answer_value: scaleOptions.find((o) => o.value === selectedScale)?.label || '',
      },
      {
        question_code: 'risk_profile',
        question_text: '손실 감수도',
        answer_value: riskOptions.find((o) => o.value === selectedRisk)?.label || '',
      },
      {
        question_code: 'interests_details',
        question_text: '상세 관심사',
        answer_value: selectedInterests.join(', '),
      },
    ];

    try {
      const response = await profileMutation.mutateAsync({
        experience_level: (selectedExperience as any) || 'beginner',
        risk_profile: (selectedRisk as any) || 'steady',
        learning_goal: mappedGoal,
        preferred_style: 'gentle',
        interests: interestsPayload as any,
        answers: answersPayload,
      });

      // Construct Recommendations List from Backend
      const apiRecs = (response.recommended_mentors || []).map((m, idx) => ({
        id: m.id,
        slug: m.slug,
        name: m.name,
        title: m.title,
        oneLiner: m.summary,
        philosophy: m.summary,
        idealFor: m.reason,
        accentColor:
          m.id === 1
            ? '#2D6A4F'
            : m.id === 2
              ? '#C66B5A'
              : m.id === 4
                ? '#D9822B'
                : '#355CDE',
        focusTags: [],
        experienceMatch: [],
        riskMatch: [],
        styleMatch: [],
        goalMatch: [],
        strengths:
          m.id === 1
            ? ['가치투자 기초', '장기 복리 관점']
            : m.id === 2
              ? ['생활밀착형 분석', '성장주 감각']
              : m.id === 4
                ? ['추세·주도주 분석', '손절 규율과 리스크 관리']
                : ['거시 흐름 해석', '자산 배분'],
        score: response.recommended_mentors.length - idx,
        reasons: [m.reason],
      }));

      setRecommendedMentors(apiRecs);
      if (apiRecs.length > 0) {
        setSelectedMentorId(apiRecs[0].id);
      }
      setMode('mentor');
    } catch (e) {
      console.warn('API Profile Saving failed. Showing local mock matching instead.', e);
      if (!shouldUseLocalOnboardingFallback(accessToken)) {
        setSubmitError('Failed to save onboarding profile. Please try again.');
        return;
      }
      // Fallback Local recommendations mock
      const mockRecs = [
        {
          id: 1,
          slug: 'warren-buffett',
          name: '워런 버핏',
          title: '가치 투자 멘토',
          oneLiner: '장기 복리와 기업 가치의 기본을 차분히 잡아주는 가치투자 멘토',
          philosophy: '기업의 본질 가치를 알고 장기 복리 효과를 누리는 안락한 투자를 선호합니다.',
          idealFor: '안정적인 투자 기초를 쌓고 장기 관점의 판단 기준을 만들고 싶은 사용자',
          accentColor: '#2D6A4F',
          focusTags: [],
          experienceMatch: [],
          riskMatch: [],
          styleMatch: [],
          goalMatch: [],
          strengths: ['가치투자 기초', '장기 복리 관점', '안정적인 투자 습관'],
          score: 3,
          reasons: ['손실 없이 안정적인 투자 성향과 아주 어울립니다.'],
        },
        {
          id: 2,
          slug: 'peter-lynch',
          name: '피터 린치',
          title: '생활형 종목 발굴 멘토',
          oneLiner: '생활 속 단서와 쉬운 설명으로 종목 판단 감각을 키워주는 멘토',
          philosophy: '생활 속 발견이 최고의 투자처이며 주위를 세심히 관찰하는 습관이 중요합니다.',
          idealFor: '뉴스와 기업 사례를 연결해서 개별 종목 감각을 키우고 싶은 사용자',
          accentColor: '#C66B5A',
          focusTags: [],
          experienceMatch: [],
          riskMatch: [],
          styleMatch: [],
          goalMatch: [],
          strengths: ['생활밀착형 기업 분석', '쉬운 사례 설명', '성장주 감각'],
          score: 2,
          reasons: ['개별 종목 발굴과 생활 속 기업 분석에 알맞습니다.'],
        },
      ];
      setRecommendedMentors(mockRecs);
      setSelectedMentorId(1);
      setMode('mentor');
    }
  }

  async function handleSelectMentor() {
    if (!selectedMentorId) return;
    setSubmitError(null);

    try {
      let finalStatus = null;
      if (accessToken) {
        finalStatus = await mentorMutation.mutateAsync({ mentor_id: selectedMentorId });
      }

      // Finish Onboarding in Zustand
      finishOnboarding({
        profile: {
          experienceLevel: (selectedExperience as any) || 'beginner',
          interests: selectedInterests as any,
          riskProfile: (selectedRisk as any) || 'steady',
          learningGoal: mapGoalToBackend(selectedGoals),
          preferredStyle: 'gentle',
          selectedMentorId: selectedMentorId,
          completedAt: new Date().toISOString(),
          syncState: accessToken ? 'remote' : 'local',
        },
        source: accessToken ? 'remote' : 'local',
      });

      if (accessToken && finalStatus) {
        queryClient.setQueryData(['onboarding-status', accessToken], finalStatus);
      }
    } catch (e) {
      console.error('Mentor selection failed', e);
      if (!shouldUseLocalOnboardingFallback(accessToken)) {
        setSubmitError('Failed to save mentor selection. Please try again.');
        return;
      }
      // Fallback complete onboarding locally
      finishOnboarding({
        profile: {
          experienceLevel: (selectedExperience as any) || 'beginner',
          interests: selectedInterests as any,
          riskProfile: (selectedRisk as any) || 'steady',
          learningGoal: mapGoalToBackend(selectedGoals),
          preferredStyle: 'gentle',
          selectedMentorId: selectedMentorId,
          completedAt: new Date().toISOString(),
          syncState: 'local',
        },
        source: 'local',
      });
    }
  }

  // UI Strings
  const stepTitles = [
    '연령대가\n어떻게 되시나요?',
    '투자 경험이\n있으신가요?',
    '투자 관심 이유가\n무엇인가요?',
    '투자 자산 규모가\n어느 정도인가요?',
    '손실을 어느 정도\n감안할 수 있나요?',
    '어떤 주제에\n관심이 있으신가요?',
  ];

  const stepSubtitles = [
    '안녕하세요, 투자자님!',
    '답변에 맞춰 멘토의 설명 깊이를 조절할게요.',
    '복수 선택 가능해요',
    '보다 정확한 자산 멘토링 매칭을 위한 질문이에요.',
    '안정감과 수익률의 밸런스를 맞추기 위함입니다.',
    '복수 선택 가능해요. 관심사 기반으로 멘토를 추천해 드려요.',
  ];

  return (
    <SafeAreaView style={styles.screen}>
      {/* ProgressBar Top Header */}
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          {step > 1 || mode === 'mentor' ? (
            <Pressable onPress={handleBack} hitSlop={12} style={styles.backButton}>
              <Text style={styles.backButtonText}>←</Text>
            </Pressable>
          ) : (
            <View style={styles.backButtonPlaceholder} />
          )}
          <Text style={styles.headerStepText}>
            {mode === 'mentor' ? '멘토 선택' : `${step} / 6`}
          </Text>
        </View>

        {mode === 'survey' ? (
          <View style={styles.progressTrack}>
            <View style={[styles.progressFill, { width: `${(step / 6) * 100}%` }]} />
          </View>
        ) : null}
      </View>

      {/* Floating White Card Content Sheet */}
      <View style={styles.sheet}>
        {mode === 'survey' ? (
          <>
            <ScrollView
              contentContainerStyle={styles.scrollContent}
              showsVerticalScrollIndicator={false}
            >
              <Text style={styles.subtitle}>{stepSubtitles[step - 1]}</Text>
              <Text style={styles.title}>{stepTitles[step - 1]}</Text>
              {submitError ? <Text style={styles.errorText}>{submitError}</Text> : null}

              {/* Step 1: Age Selection */}
              {step === 1 && (
                <View style={styles.optionList}>
                  {ageOptions.map((opt) => (
                    <Pressable
                      key={opt.value}
                      onPress={() => setSelectedAge(opt.value)}
                      style={[
                        styles.optionRow,
                        selectedAge === opt.value && styles.optionRowSelected,
                      ]}
                    >
                      <View
                        style={[
                          styles.radioOuter,
                          selectedAge === opt.value && styles.radioOuterSelected,
                        ]}
                      >
                        {selectedAge === opt.value ? <View style={styles.radioInner} /> : null}
                      </View>
                      <Text style={styles.optionLabel}>{opt.label}</Text>
                    </Pressable>
                  ))}
                </View>
              )}

              {/* Step 2: Experience Level */}
              {step === 2 && (
                <View style={styles.optionList}>
                  {experienceOptions.map((opt) => (
                    <Pressable
                      key={opt.value}
                      onPress={() => setSelectedExperience(opt.value)}
                      style={[
                        styles.optionRow,
                        selectedExperience === opt.value && styles.optionRowSelected,
                      ]}
                    >
                      <View
                        style={[
                          styles.radioOuter,
                          selectedExperience === opt.value && styles.radioOuterSelected,
                        ]}
                      >
                        {selectedExperience === opt.value ? (
                          <View style={styles.radioInner} />
                        ) : null}
                      </View>
                      <View style={styles.labelGroup}>
                        <Text style={styles.optionLabelBold}>{opt.label}</Text>
                        <Text style={styles.optionDescription}>{opt.description}</Text>
                      </View>
                    </Pressable>
                  ))}
                </View>
              )}

              {/* Step 3: Goals Checkbox Selection */}
              {step === 3 && (
                <View style={styles.optionList}>
                  {goalOptions.map((opt) => {
                    const isSelected = selectedGoals.includes(opt.value);
                    return (
                      <Pressable
                        key={opt.value}
                        onPress={() => handleGoalToggle(opt.value)}
                        style={[styles.optionRow, isSelected && styles.optionRowSelected]}
                      >
                        <View
                          style={[styles.checkboxOuter, isSelected && styles.checkboxOuterSelected]}
                        >
                          {isSelected ? <Text style={styles.checkmark}>✓</Text> : null}
                        </View>
                        <Text style={styles.optionLabel}>{opt.label}</Text>
                      </Pressable>
                    );
                  })}
                </View>
              )}

              {/* Step 4: Scale Selection */}
              {step === 4 && (
                <View style={styles.optionList}>
                  {scaleOptions.map((opt) => (
                    <Pressable
                      key={opt.value}
                      onPress={() => setSelectedScale(opt.value)}
                      style={[
                        styles.optionRow,
                        selectedScale === opt.value && styles.optionRowSelected,
                      ]}
                    >
                      <View
                        style={[
                          styles.radioOuter,
                          selectedScale === opt.value && styles.radioOuterSelected,
                        ]}
                      >
                        {selectedScale === opt.value ? <View style={styles.radioInner} /> : null}
                      </View>
                      <Text style={styles.optionLabel}>{opt.label}</Text>
                    </Pressable>
                  ))}
                </View>
              )}

              {/* Step 5: Risk Selection */}
              {step === 5 && (
                <View style={styles.optionList}>
                  {riskOptions.map((opt) => (
                    <Pressable
                      key={opt.value}
                      onPress={() => setSelectedRisk(opt.value)}
                      style={[
                        styles.optionRow,
                        selectedRisk === opt.value && styles.optionRowSelected,
                      ]}
                    >
                      <View
                        style={[
                          styles.radioOuter,
                          selectedRisk === opt.value && styles.radioOuterSelected,
                        ]}
                      >
                        {selectedRisk === opt.value ? <View style={styles.radioInner} /> : null}
                      </View>
                      <View style={styles.labelGroup}>
                        <Text style={styles.optionLabelBold}>{opt.label}</Text>
                        <Text style={styles.optionDescription}>{opt.description}</Text>
                      </View>
                    </Pressable>
                  ))}
                </View>
              )}

              {/* Step 6: Simple Flat Interest Chips */}
              {step === 6 && (
                <View style={styles.interestContainer}>
                  <View style={styles.chipsWrap}>
                    {simpleInterestOptions.map((opt) => {
                      const isSelected = selectedInterests.includes(opt.value);
                      return (
                        <Pressable
                          key={opt.value}
                          onPress={() => toggleChildInterest(opt.value)}
                          style={[
                            styles.interestChip,
                            isSelected && styles.interestChipSelected,
                          ]}
                        >
                          <Text
                            style={[
                              styles.interestChipLabel,
                              isSelected && styles.interestChipLabelSelected,
                            ]}
                          >
                            {opt.label}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                  <Text style={styles.interestHint}>
                    관심 분야를 하나 이상 선택해 주세요. 설정에서 세부 항목을 더 추가할 수 있어요.
                  </Text>
                </View>
              )}
            </ScrollView>

            {/* Footer Next Button */}
            <View style={styles.footer}>
              <Pressable
                disabled={!isStepValid() || profileMutation.isPending}
                onPress={handleNextStep}
                style={[
                  styles.primaryButton,
                  (!isStepValid() || profileMutation.isPending) && styles.buttonDisabled,
                ]}
              >
                {profileMutation.isPending ? (
                  <ActivityIndicator color={colors.surface} />
                ) : (
                  <Text style={styles.primaryButtonText}>{step === 6 ? '시작하기' : '다음'}</Text>
                )}
              </Pressable>
            </View>
          </>
        ) : (
          /* Recommended Mentors Result Screen */
          <>
            <ScrollView
              contentContainerStyle={styles.scrollContent}
              showsVerticalScrollIndicator={false}
            >
              <Text style={styles.subtitle}>분석 완료!</Text>
              <Text style={styles.title}>투자 설향 분석 결과로 추천하는 멘토들입니다</Text>
              <Text style={styles.helperText}>같이 학습을 시작할 멘토를 탭하여 선택해 주세요.</Text>
              {submitError ? <Text style={styles.errorText}>{submitError}</Text> : null}

              <View style={styles.mentorList}>
                {recommendedMentors.map((mentor) => (
                  <LocalMentorCard
                    key={mentor.id}
                    mentor={mentor}
                    selected={selectedMentorId === mentor.id}
                    onPress={() => setSelectedMentorId(mentor.id)}
                  />
                ))}
              </View>
            </ScrollView>

            <View style={styles.footerRow}>
              <Pressable
                disabled={mentorMutation.isPending}
                onPress={handleSelectMentor}
                style={[
                  styles.primaryButton,
                  styles.flexAction,
                  mentorMutation.isPending && styles.buttonDisabled,
                ]}
              >
                {mentorMutation.isPending ? (
                  <ActivityIndicator color={colors.surface} />
                ) : (
                  <Text style={styles.primaryButtonText}>이 멘토로 시작하기</Text>
                )}
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
    fontSize: 13,
    fontWeight: '600',
  },
  progressTrack: {
    backgroundColor: 'rgba(255, 255, 255, 0.25)',
    borderRadius: 999,
    height: 4,
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: {
    backgroundColor: colors.surface,
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
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 32,
  },
  subtitle: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 6,
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    lineHeight: 32,
    marginBottom: 20,
  },
  optionList: {
    gap: 12,
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
    minHeight: 56,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  optionRowSelected: {
    borderColor: colors.primary,
    backgroundColor: 'rgba(45, 106, 79, 0.03)',
  },
  radioOuter: {
    alignItems: 'center',
    borderColor: colors.border,
    borderWidth: 1.5,
    borderRadius: 999,
    height: 20,
    justifyContent: 'center',
    width: 20,
  },
  radioOuterSelected: {
    borderColor: colors.primary,
  },
  radioInner: {
    backgroundColor: colors.primary,
    borderRadius: 999,
    height: 10,
    width: 10,
  },
  checkboxOuter: {
    alignItems: 'center',
    borderColor: colors.border,
    borderWidth: 1.5,
    borderRadius: 4,
    height: 20,
    justifyContent: 'center',
    width: 20,
  },
  checkboxOuterSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  checkmark: {
    color: colors.surface,
    fontSize: 12,
    fontWeight: 'bold',
    lineHeight: 14,
  },
  optionLabel: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '500',
  },
  optionLabelBold: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 4,
  },
  optionDescription: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
  },
  labelGroup: {
    flex: 1,
  },
  interestContainer: {
    gap: 16,
  },
  interestHint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 8,
  },
  categoryCard: {
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  categoryHeader: {
    alignItems: 'center',
    backgroundColor: '#F8F9F8',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  categoryHeaderSelected: {
    backgroundColor: 'rgba(45, 106, 79, 0.05)',
  },
  categoryTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  categoryCheck: {
    alignItems: 'center',
    borderColor: colors.border,
    borderWidth: 1.5,
    borderRadius: 4,
    height: 18,
    justifyContent: 'center',
    width: 18,
  },
  categoryCheckSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
  checkmarkMini: {
    color: colors.surface,
    fontSize: 10,
    fontWeight: 'bold',
    lineHeight: 12,
  },
  chipsWrap: {
    backgroundColor: colors.surface,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 14,
  },
  interestChip: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  interestChipSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  interestChipLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '500',
  },
  interestChipLabelSelected: {
    color: colors.primary,
    fontWeight: '700',
  },
  customInterestCard: {
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    gap: 12,
  },
  customInterestTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
  },
  customInput: {
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    height: 40,
    paddingHorizontal: 12,
    fontSize: 13,
  },
  customAddBtn: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    justifyContent: 'center',
    paddingHorizontal: 16,
  },
  customAddBtnText: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '700',
  },
  footer: {
    backgroundColor: colors.surface,
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 8,
  },
  footerRow: {
    backgroundColor: colors.surface,
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 8,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 14,
    minHeight: 64,
    height: 52,
    justifyContent: 'center',
    width: '100%',
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 2,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  flexAction: {
    flex: 1,
  },
  helperText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 20,
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 16,
  },
  mentorList: {
    gap: 16,
  },
});
