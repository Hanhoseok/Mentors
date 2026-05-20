import { useEffect } from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
import { getOnboardingStatus } from '@/features/onboarding/api';
import {
  getExperienceLevelLabel,
  getInterestLabel,
  getLearningGoalLabel,
  getPreferredStyleLabel,
  getRiskProfileLabel,
} from '@/features/onboarding/data';
import { getMentorById } from '@/features/onboarding/logic';
import { OnboardingScreen } from '@/features/onboarding/screens/OnboardingScreen';
import { useUserStore } from '@/store/userStore';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

function HomeScreen() {
  const onboardingProfile = useUserStore((state) => state.onboardingProfile);
  const onboardingSource = useUserStore((state) => state.onboardingSource);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);
  const selectedMentor = onboardingProfile
    ? getMentorById(onboardingProfile.selectedMentorId)
    : null;

  return (
    <ScrollView contentContainerStyle={styles.homeContainer}>
      <View style={styles.heroCard}>
        <Text style={styles.eyebrow}>Mentors Home</Text>
        <Text style={styles.heroTitle}>첫 멘토링 설정이 준비됐어요.</Text>
        <Text style={styles.heroDescription}>
          온보딩에서 고른 성향을 바탕으로 홈에서 이어서 학습, 토론, 리포트를 붙일 수 있도록 구조를
          먼저 열어뒀습니다.
        </Text>
        <View
          style={[
            styles.syncBadge,
            onboardingSource === 'remote' ? styles.syncBadgeRemote : styles.syncBadgeLocal,
          ]}
        >
          <Text style={styles.syncBadgeText}>
            {onboardingSource === 'remote'
              ? '서버 온보딩 상태와 동기화됨'
              : '로컬 데모 모드로 저장됨'}
          </Text>
        </View>
      </View>

      {selectedMentor ? (
        <View style={styles.summaryCard}>
          <Text style={styles.sectionTitle}>선택한 멘토</Text>
          <Text style={styles.mentorName}>{selectedMentor.name}</Text>
          <Text style={styles.mentorTitle}>{selectedMentor.title}</Text>
          <Text style={styles.summaryText}>{selectedMentor.philosophy}</Text>
        </View>
      ) : null}

      {onboardingProfile ? (
        <View style={styles.summaryCard}>
          <Text style={styles.sectionTitle}>저장된 성향 요약</Text>
          <View style={styles.detailList}>
            <Text style={styles.detailItem}>
              투자 경험: {getExperienceLevelLabel(onboardingProfile.experienceLevel)}
            </Text>
            <Text style={styles.detailItem}>
              리스크 성향: {getRiskProfileLabel(onboardingProfile.riskProfile)}
            </Text>
            <Text style={styles.detailItem}>
              학습 목표: {getLearningGoalLabel(onboardingProfile.learningGoal)}
            </Text>
            <Text style={styles.detailItem}>
              선호 코칭: {getPreferredStyleLabel(onboardingProfile.preferredStyle)}
            </Text>
            <Text style={styles.detailItem}>
              관심사: {onboardingProfile.interests.map(getInterestLabel).join(', ')}
            </Text>
          </View>
        </View>
      ) : (
        <View style={styles.summaryCard}>
          <Text style={styles.sectionTitle}>서버 상태로 완료된 사용자</Text>
          <Text style={styles.summaryText}>
            현재는 서버에서 온보딩 완료 여부만 내려주기 때문에, 세부 프로필은 이후 API가 열리면 이
            카드에 채워질 수 있게 준비해 두었습니다.
          </Text>
        </View>
      )}

      <Pressable onPress={resetOnboarding} style={styles.resetButton}>
        <Text style={styles.resetButtonText}>온보딩 다시 보기</Text>
      </Pressable>
    </ScrollView>
  );
}

export function RootNavigator() {
  const accessToken = useUserStore((state) => state.accessToken);
  const hasCompletedOnboarding = useUserStore((state) => state.hasCompletedOnboarding);
  const finishOnboarding = useUserStore((state) => state.finishOnboarding);
  const onboardingStatusQuery = useQuery({
    queryKey: ['onboarding-status', accessToken],
    queryFn: getOnboardingStatus,
    enabled: Boolean(accessToken) && !hasCompletedOnboarding,
    retry: 0,
  });

  useEffect(() => {
    if (onboardingStatusQuery.data?.onboarded && !hasCompletedOnboarding) {
      finishOnboarding({
        profile: null,
        source: 'remote',
      });
    }
  }, [finishOnboarding, hasCompletedOnboarding, onboardingStatusQuery.data]);

  const isCheckingRemoteStatus =
    Boolean(accessToken) && !hasCompletedOnboarding && onboardingStatusQuery.isLoading;

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {isCheckingRemoteStatus ? (
        <Stack.Screen name="Onboarding">
          {() => (
            <View style={styles.loadingContainer}>
              <Text style={styles.loadingTitle}>기존 온보딩 상태를 확인하고 있어요.</Text>
              <Text style={styles.loadingDescription}>
                서버 정보가 없거나 아직 스텁이면 바로 온보딩 화면으로 이어집니다.
              </Text>
            </View>
          )}
        </Stack.Screen>
      ) : hasCompletedOnboarding ? (
        <Stack.Screen name="Home" component={HomeScreen} />
      ) : (
        <Stack.Screen name="Onboarding" component={OnboardingScreen} />
      )}
    </Stack.Navigator>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 28,
    backgroundColor: colors.background,
  },
  loadingTitle: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 12,
  },
  loadingDescription: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  homeContainer: {
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
    lineHeight: 34,
  },
  heroDescription: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  syncBadge: {
    alignSelf: 'flex-start',
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  syncBadgeRemote: {
    backgroundColor: colors.primarySoft,
  },
  syncBadgeLocal: {
    backgroundColor: colors.accentSoft,
  },
  syncBadgeText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 10,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  mentorName: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  mentorTitle: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '600',
  },
  summaryText: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
  detailList: {
    gap: 8,
  },
  detailItem: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  resetButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 18,
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  resetButtonText: {
    color: colors.surface,
    fontSize: 15,
    fontWeight: '700',
  },
});
