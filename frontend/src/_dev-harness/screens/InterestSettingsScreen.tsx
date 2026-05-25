import { useEffect, useMemo, useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import { type NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
import { getAuthApiErrorMessage } from '@/features/auth/api';
import { getOnboardingStatus, saveOnboardingProfile } from '@/features/onboarding/api';
import type { InterestTag } from '@/features/onboarding/types';
import { useUserStore } from '@/store/userStore';
import { getInterestLabel, profileInterestOptions } from '../onboarding/data';
import { toggleInterest } from '../onboarding/logic';
import type { RootStackParamList } from '../navigation/types';
import {
  buildLearningPreferenceSeed,
  buildLearningPreferencesPayload,
  hasLearningPreferenceChanges,
} from '../settings/logic';

type InterestSettingsNavigation = NativeStackNavigationProp<
  RootStackParamList,
  'InterestSettings'
>;

function InterestPill({
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
        styles.pill,
        selected ? styles.pillSelected : styles.pillIdle,
        pressed && styles.pillPressed,
      ]}
    >
      <Text style={[styles.pillLabel, selected && styles.pillLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

export function InterestSettingsScreen() {
  const accessToken = useUserStore((state) => state.accessToken);
  const navigation = useNavigation<InterestSettingsNavigation>();
  const queryClient = useQueryClient();

  const [selectedInterests, setSelectedInterests] = useState<InterestTag[]>([]);
  const [hydratedPreferenceSeed, setHydratedPreferenceSeed] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const onboardingStatusQuery = useQuery({
    queryKey: ['onboarding-status', accessToken],
    queryFn: getOnboardingStatus,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  const profile = onboardingStatusQuery.data?.profile ?? null;
  const profilePreferenceSeed =
    profile === null
      ? null
      : buildLearningPreferenceSeed({
          interests: profile.interests,
          preferredStyle: profile.preferred_style,
        });

  useEffect(() => {
    if (!profile || !profilePreferenceSeed || profilePreferenceSeed === hydratedPreferenceSeed) {
      return;
    }

    setSelectedInterests(profile.interests);
    setHydratedPreferenceSeed(profilePreferenceSeed);
  }, [hydratedPreferenceSeed, profile, profilePreferenceSeed]);

  const saveInterestsMutation = useMutation({
    mutationFn: saveOnboardingProfile,
    onSuccess: async () => {
      setFeedbackMessage('관심사를 저장했어요.');
      await queryClient.invalidateQueries({ queryKey: ['onboarding-status', accessToken] });
      navigation.goBack();
    },
    onError: (error) => {
      setFeedbackMessage(
        getAuthApiErrorMessage(error, '관심사를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.'),
      );
    },
  });

  const selectedCount = selectedInterests.length;
  const selectedSummary = useMemo(
    () => selectedInterests.map(getInterestLabel).slice(0, 3).join(', '),
    [selectedInterests],
  );

  const isDirty =
    profile !== null &&
    hasLearningPreferenceChanges(profile, {
      interests: selectedInterests,
      preferredStyle: profile.preferred_style,
    });

  function handleToggleInterest(nextInterest: InterestTag) {
    setFeedbackMessage(null);
    setSelectedInterests((current) => {
      const next = toggleInterest(current, nextInterest);
      return next.length === 0 ? current : next;
    });
  }

  function handleSave() {
    if (!profile || selectedInterests.length === 0) {
      return;
    }

    setFeedbackMessage(null);
    saveInterestsMutation.mutate(
      buildLearningPreferencesPayload(profile, {
        interests: selectedInterests,
        preferredStyle: profile.preferred_style,
      }),
    );
  }

  function handleCustomInterestPress() {
    setFeedbackMessage('직접 입력 관심사는 다음 단계에서 지원할 예정이에요.');
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backButton}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>관심사 설정</Text>
      </View>

      {onboardingStatusQuery.isLoading ? (
        <View style={styles.loadingState}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <>
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            <Text style={styles.description}>
              선택한 주제 기반으로 리포트와 뉴스가 추천돼요
            </Text>
            <Text style={styles.countLabel}>현재 {selectedCount}개 선택됨</Text>

            <View style={styles.pillGrid}>
              {profileInterestOptions.map((option) => (
                <InterestPill
                  key={option.value}
                  label={option.label}
                  selected={selectedInterests.includes(option.value)}
                  onPress={() => handleToggleInterest(option.value)}
                />
              ))}
              <InterestPill
                label="+ 직접 입력"
                selected={false}
                onPress={handleCustomInterestPress}
              />
            </View>

            {selectedSummary ? <Text style={styles.summaryText}>{selectedSummary}</Text> : null}
            {feedbackMessage ? <Text style={styles.feedbackText}>{feedbackMessage}</Text> : null}
          </ScrollView>

          <View style={styles.footer}>
            <Pressable
              disabled={!isDirty || saveInterestsMutation.isPending}
              onPress={handleSave}
              style={({ pressed }) => [
                styles.saveButton,
                (!isDirty || saveInterestsMutation.isPending) && styles.saveButtonDisabled,
                pressed && isDirty && !saveInterestsMutation.isPending && styles.pillPressed,
              ]}
            >
              <Text style={styles.saveButtonText}>
                {saveInterestsMutation.isPending ? '저장 중...' : '저장'}
              </Text>
            </Pressable>
          </View>
        </>
      )}
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
  },
  backButton: {
    alignItems: 'center',
    height: 32,
    justifyContent: 'center',
    marginRight: 8,
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
    fontWeight: '600',
  },
  loadingState: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 128,
  },
  description: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
  },
  countLabel: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '500',
    marginTop: 14,
  },
  pillGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 18,
  },
  pill: {
    borderRadius: 16,
    borderWidth: 1,
    minHeight: 32,
    justifyContent: 'center',
    paddingHorizontal: 15,
    paddingVertical: 7,
  },
  pillIdle: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  pillSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pillPressed: {
    opacity: 0.88,
  },
  pillLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '500',
  },
  pillLabelSelected: {
    color: colors.surface,
  },
  summaryText: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 16,
  },
  feedbackText: {
    color: colors.primary,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 12,
  },
  footer: {
    backgroundColor: colors.surface,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    bottom: 0,
    left: 0,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 20,
    position: 'absolute',
    right: 0,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
  },
  saveButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 14,
    justifyContent: 'center',
    minHeight: 52,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
  },
  saveButtonDisabled: {
    opacity: 0.45,
  },
  saveButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
});
