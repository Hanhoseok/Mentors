import { useEffect, useState, type ReactNode } from 'react';
import { useNavigation } from '@react-navigation/native';
import { type NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { deleteCurrentUser, getAuthApiErrorMessage, getCurrentUser } from '@/features/auth/api';
import {
  resetOnboardingProfile,
  getOnboardingStatus,
  saveOnboardingProfile,
} from '@/features/onboarding/api';
import type { InterestTag, PreferredStyle } from '@/features/onboarding/types';
import { useUserStore } from '@/store/userStore';
import { SelectionChip } from '../components/SelectionChip';
import type { RootStackParamList } from '../navigation/types';
import {
  getExperienceLevelLabel,
  getInterestLabel,
  getLearningGoalLabel,
  getPreferredStyleLabel,
  getRiskProfileLabel,
  preferredStyleOptions,
} from '../onboarding/data';
import {
  buildLearningPreferenceSeed,
  hasLearningPreferenceChanges,
  buildLearningPreferencesPayload,
  formatReminderTime,
  shiftReminderTime,
} from '../settings/logic';
import {
  ensureReminderPermissionsAsync,
  syncReminderNotifications,
} from '../settings/notifications';
import { type ReminderPreferences, useSettingsStore } from '../store/settingsStore';

const QUICK_REMINDER_TIMES = ['08:00', '12:30', '19:00', '21:00'] as const;
type SettingsNavigation = NativeStackNavigationProp<RootStackParamList, 'Settings'>;

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
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <Text style={styles.sectionDescription}>{description}</Text>
      </View>
      <View style={styles.sectionBody}>{children}</View>
    </View>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.summaryRow}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue}>{value}</Text>
    </View>
  );
}

function ActionButton({
  label,
  tone = 'default',
  disabled = false,
  onPress,
}: {
  label: string;
  tone?: 'default' | 'primary' | 'danger';
  disabled?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionButton,
        tone === 'primary' && styles.actionButtonPrimary,
        tone === 'danger' && styles.actionButtonDanger,
        disabled && styles.actionButtonDisabled,
        pressed && !disabled && styles.actionButtonPressed,
      ]}
    >
      <Text
        style={[
          styles.actionButtonText,
          tone === 'primary' && styles.actionButtonTextPrimary,
          tone === 'danger' && styles.actionButtonTextDanger,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

function NotificationRow({
  title,
  description,
  value,
  onValueChange,
}: {
  title: string;
  description: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
}) {
  return (
    <View style={styles.notificationRow}>
      <View style={styles.notificationTextGroup}>
        <Text style={styles.notificationTitle}>{title}</Text>
        <Text style={styles.notificationDescription}>{description}</Text>
      </View>
      <Switch
        trackColor={{ false: '#D8DDD8', true: '#9AD4BD' }}
        thumbColor={value ? colors.primary : colors.surface}
        value={value}
        onValueChange={onValueChange}
      />
    </View>
  );
}

function showConfirmationDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
}) {
  if (
    Platform.OS === 'web' &&
    typeof window !== 'undefined' &&
    typeof window.confirm === 'function'
  ) {
    if (window.confirm(`${title}\n\n${message}`)) {
      onConfirm();
    }
    return;
  }

  Alert.alert(title, message, [
    { text: '취소', style: 'cancel' },
    {
      text: confirmLabel,
      style: 'destructive',
      onPress: onConfirm,
    },
  ]);
}

export function SettingsScreen() {
  const accessToken = useUserStore((state) => state.accessToken);
  const clearToken = useUserStore((state) => state.clearToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);
  const navigation = useNavigation<SettingsNavigation>();
  const queryClient = useQueryClient();

  const learningReminderEnabled = useSettingsStore((state) => state.learningReminderEnabled);
  const dailyReportReminderEnabled = useSettingsStore((state) => state.dailyReportReminderEnabled);
  const reminderTime = useSettingsStore((state) => state.reminderTime);
  const setLearningReminderEnabled = useSettingsStore((state) => state.setLearningReminderEnabled);
  const setDailyReportReminderEnabled = useSettingsStore(
    (state) => state.setDailyReportReminderEnabled,
  );
  const setReminderTime = useSettingsStore((state) => state.setReminderTime);
  const resetSettings = useSettingsStore((state) => state.reset);

  const [selectedInterests, setSelectedInterests] = useState<InterestTag[]>([]);
  const [selectedStyle, setSelectedStyle] = useState<PreferredStyle | null>(null);
  const [hydratedPreferenceSeed, setHydratedPreferenceSeed] = useState<string | null>(null);
  const [learningSaveMessage, setLearningSaveMessage] = useState<string | null>(null);
  const [notificationMessage, setNotificationMessage] = useState<string | null>(null);

  const userQuery = useQuery({
    queryKey: ['auth-me', accessToken],
    queryFn: getCurrentUser,
    enabled: Boolean(accessToken),
    retry: 0,
  });

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
    setSelectedStyle(profile.preferred_style);
    setHydratedPreferenceSeed(profilePreferenceSeed);
  }, [hydratedPreferenceSeed, profile, profilePreferenceSeed]);

  const saveLearningMutation = useMutation({
    mutationFn: saveOnboardingProfile,
    onSuccess: async () => {
      setLearningSaveMessage('학습 설정을 저장했어요.');
      await queryClient.invalidateQueries({ queryKey: ['onboarding-status', accessToken] });
    },
    onError: (error) => {
      setLearningSaveMessage(
        getAuthApiErrorMessage(error, '학습 설정을 저장하지 못했어요. 잠시 후 다시 시도해주세요.'),
      );
    },
  });

  const resetOnboardingMutation = useMutation({
    mutationFn: resetOnboardingProfile,
    onSuccess: async () => {
      setLearningSaveMessage(null);
      await queryClient.invalidateQueries({ queryKey: ['onboarding-status', accessToken] });
      resetOnboarding();
    },
    onError: (error) => {
      setLearningSaveMessage(
        getAuthApiErrorMessage(
          error,
          '온보딩을 다시 시작하지 못했어요. 잠시 후 다시 시도해 주세요.',
        ),
      );
    },
  });

  const deleteAccountMutation = useMutation({
    mutationFn: deleteCurrentUser,
    onSuccess: () => {
      resetSettings();
      clearToken();
      queryClient.clear();
    },
  });

  const isLearningDirty =
    profile !== null &&
    selectedStyle !== null &&
    hasLearningPreferenceChanges(profile, {
      interests: selectedInterests,
      preferredStyle: selectedStyle,
    });
  const interestSummary =
    selectedInterests.length > 0
      ? selectedInterests.map(getInterestLabel).slice(0, 3).join(', ')
      : '아직 선택한 관심사가 없어요.';

  const reminderPreferences: ReminderPreferences = {
    learningReminderEnabled,
    dailyReportReminderEnabled,
    reminderTime,
  };

  async function applyReminderPreferences(nextPreferences: ReminderPreferences): Promise<void> {
    try {
      const needsPermission =
        nextPreferences.learningReminderEnabled || nextPreferences.dailyReportReminderEnabled;

      if (needsPermission) {
        const granted = await ensureReminderPermissionsAsync();
        if (!granted) {
          setNotificationMessage('알림 권한이 없어 설정을 적용하지 못했어요.');
          return;
        }
      }

      setLearningReminderEnabled(nextPreferences.learningReminderEnabled);
      setDailyReportReminderEnabled(nextPreferences.dailyReportReminderEnabled);
      setReminderTime(nextPreferences.reminderTime);
      await syncReminderNotifications(nextPreferences);
      setNotificationMessage('알림 설정을 적용했어요.');
    } catch (error) {
      setNotificationMessage(
        getAuthApiErrorMessage(
          error,
          '알림 설정을 적용하지 못했어요. 기기 권한을 다시 확인해주세요.',
        ),
      );
    }
  }

  function handleSaveLearningSettings() {
    if (!profile || !selectedStyle || selectedInterests.length === 0) {
      return;
    }

    setLearningSaveMessage(null);
    saveLearningMutation.mutate(
      buildLearningPreferencesPayload(profile, {
        interests: selectedInterests,
        preferredStyle: selectedStyle,
      }),
    );
  }

  function handleLogout() {
    clearToken();
    queryClient.clear();
  }

  // Retained for native alert fallback reference while web-safe confirm flow is wired separately.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function handleResetOnboarding() {
    Alert.alert(
      '온보딩을 다시 시작할까요?',
      '현재 선택한 관심 주제와 설명 스타일, 멘토 선택이 초기화되고 온보딩 화면으로 돌아가요.',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '다시 시작',
          style: 'destructive',
          onPress: () => resetOnboardingMutation.mutate(),
        },
      ],
    );
  }

  // Retained for native alert fallback reference while web-safe confirm flow is wired separately.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  function handleDeleteAccount() {
    Alert.alert(
      '계정을 삭제할까요?',
      '삭제 후에는 현재 계정으로 다시 학습 기록을 이어갈 수 없어요.',
      [
        { text: '취소', style: 'cancel' },
        {
          text: '삭제',
          style: 'destructive',
          onPress: () => deleteAccountMutation.mutate(),
        },
      ],
    );
  }

  function confirmResetOnboarding() {
    showConfirmationDialog({
      title: '온보딩을 다시 시작할까요?',
      message:
        '현재 선택한 관심 주제와 설명 스타일, 멘토 선택이 초기화되고 온보딩 화면으로 돌아가요.',
      confirmLabel: '다시 시작',
      onConfirm: () => resetOnboardingMutation.mutate(),
    });
  }

  function confirmDeleteAccount() {
    showConfirmationDialog({
      title: '계정을 삭제할까요?',
      message: '삭제 후에는 현재 계정으로 다시 학습 기록을 이어갈 수 없어요.',
      confirmLabel: '삭제',
      onConfirm: () => deleteAccountMutation.mutate(),
    });
  }

  async function handleReminderToggle(
    key: 'learningReminderEnabled' | 'dailyReportReminderEnabled',
    nextValue: boolean,
  ) {
    const nextPreferences: ReminderPreferences = {
      ...reminderPreferences,
      [key]: nextValue,
    };
    await applyReminderPreferences(nextPreferences);
  }

  async function handleReminderTimeChange(nextTime: string) {
    const nextPreferences: ReminderPreferences = {
      ...reminderPreferences,
      reminderTime: formatReminderTime(nextTime),
    };
    await applyReminderPreferences(nextPreferences);
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Text style={styles.heroEyebrow}>개인 설정</Text>
          <Text style={styles.heroTitle}>내 학습 환경을 정리해보세요</Text>
          <Text style={styles.heroDescription}>
            계정 정보, 학습 취향, 리마인드 시간을 한곳에서 관리할 수 있어요.
          </Text>
        </View>

        <Section
          title="계정"
          description="현재 로그인 계정과 학습 프로필 요약을 빠르게 확인할 수 있어요."
        >
          <View style={styles.card}>
            {userQuery.isLoading || onboardingStatusQuery.isLoading ? (
              <View style={styles.loadingBox}>
                <ActivityIndicator color={colors.primary} />
              </View>
            ) : (
              <>
                <SummaryRow label="닉네임" value={userQuery.data?.nickname ?? '-'} />
                <SummaryRow label="이메일" value={userQuery.data?.email ?? '-'} />
                <SummaryRow
                  label="멘토"
                  value={onboardingStatusQuery.data?.selected_mentor?.name ?? '아직 선택되지 않음'}
                />
                <SummaryRow
                  label="투자 경험"
                  value={profile ? getExperienceLevelLabel(profile.experience_level) : '-'}
                />
                <SummaryRow
                  label="위험 성향"
                  value={profile ? getRiskProfileLabel(profile.risk_profile) : '-'}
                />
                <SummaryRow
                  label="학습 목표"
                  value={profile ? getLearningGoalLabel(profile.learning_goal) : '-'}
                />
                <SummaryRow
                  label="관심 주제"
                  value={profile ? profile.interests.map(getInterestLabel).join(', ') : '-'}
                />
                <SummaryRow
                  label="설명 스타일"
                  value={profile ? getPreferredStyleLabel(profile.preferred_style) : '-'}
                />
              </>
            )}
          </View>

          <View style={styles.actionColumn}>
            <ActionButton label="로그아웃" onPress={handleLogout} />
            <ActionButton
              label="채팅 기록 보기"
              onPress={() => navigation.navigate('ChatHistory')}
            />
            <ActionButton
              label={deleteAccountMutation.isPending ? '계정 삭제 중...' : '계정 삭제'}
              tone="danger"
              disabled={deleteAccountMutation.isPending}
              onPress={confirmDeleteAccount}
            />
          </View>
        </Section>

        <Section
          title="학습 설정"
          description="관심 주제와 설명 스타일을 바꿔서 멘토의 안내 톤을 다시 맞출 수 있어요."
        >
          <View style={styles.fieldBlock}>
            <Text style={styles.fieldTitle}>관심 주제</Text>
            <Pressable
              onPress={() => navigation.navigate('InterestSettings')}
              style={({ pressed }) => [
                styles.preferenceLinkCard,
                pressed && styles.actionButtonPressed,
              ]}
            >
              <View style={styles.preferenceLinkTextGroup}>
                <Text style={styles.preferenceLinkLabel}>
                  선택한 주제 기반으로 리포트와 뉴스가 추천돼요.
                </Text>
                <Text style={styles.preferenceLinkValue}>{interestSummary}</Text>
                <Text style={styles.preferenceLinkMeta}>
                  현재 {selectedInterests.length}개 선택됨
                </Text>
              </View>
              <Text style={styles.preferenceLinkArrow}>›</Text>
            </Pressable>
          </View>

          <View style={styles.fieldBlock}>
            <Text style={styles.fieldTitle}>설명 스타일</Text>
            <View style={styles.optionColumn}>
              {preferredStyleOptions.map((option) => (
                <SelectionChip
                  key={option.value}
                  label={option.label}
                  description={option.description}
                  selected={selectedStyle === option.value}
                  onPress={() => {
                    setLearningSaveMessage(null);
                    setSelectedStyle(option.value);
                  }}
                />
              ))}
            </View>
          </View>

          {learningSaveMessage ? (
            <Text style={styles.feedbackText}>{learningSaveMessage}</Text>
          ) : null}

          <View style={styles.actionColumn}>
            <ActionButton
              label={saveLearningMutation.isPending ? '저장 중...' : '학습 설정 저장'}
              tone="primary"
              disabled={!isLearningDirty || saveLearningMutation.isPending}
              onPress={handleSaveLearningSettings}
            />
            <ActionButton
              label={resetOnboardingMutation.isPending ? '온보딩 초기화 중...' : '온보딩 다시 하기'}
              disabled={resetOnboardingMutation.isPending}
              onPress={confirmResetOnboarding}
            />
          </View>
        </Section>

        <Section
          title="알림"
          description="학습 리마인드와 데일리 리포트 알림을 원하는 시간에 받아볼 수 있어요."
        >
          <View style={styles.card}>
            <NotificationRow
              title="학습 리마인드"
              description="오늘의 경제 개념 학습을 놓치지 않도록 알려드릴게요."
              value={learningReminderEnabled}
              onValueChange={(value) => {
                void handleReminderToggle('learningReminderEnabled', value);
              }}
            />
            <NotificationRow
              title="데일리 리포트 알림"
              description="오늘 시장 흐름 요약이 준비되면 같은 시간에 알려드릴게요."
              value={dailyReportReminderEnabled}
              onValueChange={(value) => {
                void handleReminderToggle('dailyReportReminderEnabled', value);
              }}
            />
          </View>

          <View style={styles.timeCard}>
            <Text style={styles.fieldTitle}>알림 시간</Text>
            <Text style={styles.timeValue}>{formatReminderTime(reminderTime)}</Text>
            <View style={styles.timeAdjustRow}>
              <ActionButton
                label="-30분"
                onPress={() => {
                  void handleReminderTimeChange(shiftReminderTime(reminderTime, -30));
                }}
              />
              <ActionButton
                label="+30분"
                onPress={() => {
                  void handleReminderTimeChange(shiftReminderTime(reminderTime, 30));
                }}
              />
            </View>
            <View style={styles.quickTimeRow}>
              {QUICK_REMINDER_TIMES.map((time) => {
                const selected = reminderTime === time;
                return (
                  <Pressable
                    key={time}
                    onPress={() => {
                      void handleReminderTimeChange(time);
                    }}
                    style={({ pressed }) => [
                      styles.quickTimeChip,
                      selected && styles.quickTimeChipSelected,
                      pressed && styles.actionButtonPressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.quickTimeChipText,
                        selected && styles.quickTimeChipTextSelected,
                      ]}
                    >
                      {time}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          {notificationMessage ? (
            <Text style={styles.feedbackText}>{notificationMessage}</Text>
          ) : null}
        </Section>
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
    gap: 24,
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 56,
  },
  hero: {
    backgroundColor: colors.primary,
    borderRadius: 28,
    paddingHorizontal: 22,
    paddingVertical: 24,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.18,
    shadowRadius: 22,
  },
  heroEyebrow: {
    color: '#D7F4E7',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  heroTitle: {
    color: colors.surface,
    fontSize: 26,
    fontWeight: '800',
    lineHeight: 32,
    marginTop: 8,
  },
  heroDescription: {
    color: '#E4F7EE',
    fontSize: 14,
    lineHeight: 21,
    marginTop: 8,
  },
  section: {
    gap: 16,
  },
  sectionHeader: {
    backgroundColor: colors.accentSoft,
    borderColor: '#F4E3B2',
    borderRadius: 18,
    borderWidth: 1,
    gap: 6,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  sectionDescription: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  sectionBody: {
    gap: 12,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    padding: 18,
    borderColor: colors.border,
    borderWidth: 1,
    shadowColor: '#14241A',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.05,
    shadowRadius: 18,
  },
  loadingBox: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 120,
  },
  summaryRow: {
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    gap: 6,
    paddingVertical: 10,
  },
  summaryLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  summaryValue: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
  actionColumn: {
    gap: 10,
  },
  actionButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    flex: 1,
    justifyContent: 'center',
    minHeight: 48,
    paddingHorizontal: 16,
  },
  actionButtonPrimary: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  actionButtonDanger: {
    backgroundColor: '#FFF2F2',
    borderColor: '#F1CACA',
  },
  actionButtonDisabled: {
    opacity: 0.45,
  },
  actionButtonPressed: {
    opacity: 0.88,
  },
  actionButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  actionButtonTextPrimary: {
    color: colors.surface,
  },
  actionButtonTextDanger: {
    color: colors.rose,
  },
  fieldBlock: {
    gap: 10,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 20,
    borderWidth: 1,
    padding: 18,
  },
  fieldTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  optionColumn: {
    gap: 10,
  },
  preferenceLinkCard: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 16,
  },
  preferenceLinkTextGroup: {
    flex: 1,
    gap: 6,
    paddingRight: 12,
  },
  preferenceLinkLabel: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  preferenceLinkValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 20,
  },
  preferenceLinkMeta: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  preferenceLinkArrow: {
    color: colors.muted,
    fontSize: 24,
    lineHeight: 24,
  },
  feedbackText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 18,
    backgroundColor: colors.primarySoft,
    borderRadius: 14,
    overflow: 'hidden',
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  notificationRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 14,
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  notificationTextGroup: {
    flex: 1,
    gap: 4,
    paddingRight: 12,
  },
  notificationTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  notificationDescription: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  timeCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    gap: 14,
    padding: 18,
    borderColor: colors.border,
    borderWidth: 1,
    shadowColor: '#14241A',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.05,
    shadowRadius: 18,
  },
  timeValue: {
    color: colors.primary,
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  timeAdjustRow: {
    flexDirection: 'row',
    gap: 10,
  },
  quickTimeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  quickTimeChip: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  quickTimeChipSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  quickTimeChipText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '700',
  },
  quickTimeChipTextSelected: {
    color: colors.primary,
  },
});
