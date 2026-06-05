import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { syncNativePushState } from '@/features/push/bootstrap';
import { useUserStore } from '@/store/userStore';
import { useSettingsStore } from '@/store/settingsStore';
import {
  ensureReminderPermissionsAsync,
  syncReminderNotifications,
} from '@/features/settings/notifications';
import {
  formatReminderTime,
  shiftReminderTime,
} from '@/features/settings/logic';
import type { AppStackParamList } from '@/navigation/types';

type Nav = NativeStackNavigationProp<AppStackParamList, 'NotificationSettings'>;

const QUICK_TIMES = ['07:00', '09:00', '12:00', '19:00', '21:00'] as const;

export function NotificationSettingsScreen() {
  const navigation = useNavigation<Nav>();
  const accessToken = useUserStore((s) => s.accessToken);

  const learningReminderEnabled = useSettingsStore((s) => s.learningReminderEnabled);
  const dailyReportReminderEnabled = useSettingsStore((s) => s.dailyReportReminderEnabled);
  const reminderTime = useSettingsStore((s) => s.reminderTime);
  const setLearningEnabled = useSettingsStore((s) => s.setLearningReminderEnabled);
  const setDailyEnabled = useSettingsStore((s) => s.setDailyReportReminderEnabled);
  const setTime = useSettingsStore((s) => s.setReminderTime);

  async function applyPrefs(
    learning: boolean,
    daily: boolean,
    time: string,
  ): Promise<void> {
    const needs = learning || daily;
    if (needs) {
      const granted = await ensureReminderPermissionsAsync();
      if (!granted) return;
      await syncNativePushState(accessToken);
    }
    setLearningEnabled(learning);
    setDailyEnabled(daily);
    setTime(time);
    await syncReminderNotifications({ learningReminderEnabled: learning, dailyReportReminderEnabled: daily, reminderTime: time });
  }

  function toggleLearning(v: boolean) {
    void applyPrefs(v, dailyReportReminderEnabled, reminderTime);
  }
  function toggleDaily(v: boolean) {
    void applyPrefs(learningReminderEnabled, v, reminderTime);
  }
  function changeTime(t: string) {
    void applyPrefs(learningReminderEnabled, dailyReportReminderEnabled, formatReminderTime(t));
  }

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>알림 설정</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* 알림 종류 */}
        <Text style={styles.sectionLabel}>알림 종류</Text>
        <View style={styles.card}>
          <View style={styles.row}>
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>학습 리마인드</Text>
              <Text style={styles.rowDesc}>오늘의 경제 개념 학습을 놓치지 않도록 알려드려요.</Text>
            </View>
            <Switch
              trackColor={{ false: '#D8DDD8', true: '#9AD4BD' }}
              thumbColor={learningReminderEnabled ? colors.primary : colors.surface}
              value={learningReminderEnabled}
              onValueChange={toggleLearning}
            />
          </View>
          <View style={styles.divider} />
          <View style={styles.row}>
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>데일리 리포트</Text>
              <Text style={styles.rowDesc}>오늘 시장 흐름 요약이 준비되면 알려드려요.</Text>
            </View>
            <Switch
              trackColor={{ false: '#D8DDD8', true: '#9AD4BD' }}
              thumbColor={dailyReportReminderEnabled ? colors.primary : colors.surface}
              value={dailyReportReminderEnabled}
              onValueChange={toggleDaily}
            />
          </View>
        </View>

        {/* 알림 시간 */}
        <Text style={styles.sectionLabel}>알림 시간</Text>
        <View style={styles.card}>
          <Text style={styles.timeValue}>{formatReminderTime(reminderTime)}</Text>
          <View style={styles.timeAdjustRow}>
            <Pressable
              onPress={() => changeTime(shiftReminderTime(reminderTime, -30))}
              style={({ pressed }) => [styles.adjBtn, pressed && styles.adjBtnPressed]}
            >
              <Text style={styles.adjBtnText}>-30분</Text>
            </Pressable>
            <Pressable
              onPress={() => changeTime(shiftReminderTime(reminderTime, 30))}
              style={({ pressed }) => [styles.adjBtn, pressed && styles.adjBtnPressed]}
            >
              <Text style={styles.adjBtnText}>+30분</Text>
            </Pressable>
          </View>
          <View style={styles.quickRow}>
            {QUICK_TIMES.map((t) => {
              const selected = reminderTime === t;
              return (
                <Pressable
                  key={t}
                  onPress={() => changeTime(t)}
                  style={[styles.quickChip, selected && styles.quickChipSelected]}
                >
                  <Text style={[styles.quickChipText, selected && styles.quickChipTextSelected]}>
                    {t}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={styles.notice}>
          <Text style={styles.noticeText}>
            알림이 정상적으로 도착하려면 기기의 알림 권한이 허용되어 있어야 해요.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  header: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 8,
    height: 56,
    paddingHorizontal: 16,
  },
  backBtn: { alignItems: 'center', height: 32, justifyContent: 'center', width: 32 },
  backArrow: { color: colors.text, fontSize: 22, fontWeight: '400' },
  headerTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  scroll: { gap: 8, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 48 },
  sectionLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.4,
    marginBottom: 4,
    marginTop: 8,
    textTransform: 'uppercase',
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
    padding: 16,
    gap: 14,
  },
  divider: {
    backgroundColor: colors.border,
    height: StyleSheet.hairlineWidth,
  },
  row: { alignItems: 'center', flexDirection: 'row', gap: 12 },
  rowText: { flex: 1, gap: 3 },
  rowTitle: { color: colors.text, fontSize: 15, fontWeight: '700' },
  rowDesc: { color: colors.muted, fontSize: 12, lineHeight: 17 },
  timeValue: {
    color: colors.primary,
    fontSize: 36,
    fontWeight: '800',
    letterSpacing: 1,
    textAlign: 'center',
  },
  timeAdjustRow: { flexDirection: 'row', gap: 10 },
  adjBtn: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 10,
    borderWidth: 1,
    flex: 1,
    justifyContent: 'center',
    paddingVertical: 12,
  },
  adjBtnPressed: { opacity: 0.8 },
  adjBtnText: { color: colors.text, fontSize: 14, fontWeight: '700' },
  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  quickChip: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  quickChipSelected: { backgroundColor: colors.primarySoft, borderColor: colors.primary },
  quickChipText: { color: colors.muted, fontSize: 13, fontWeight: '700' },
  quickChipTextSelected: { color: colors.primary },
  notice: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 8,
    padding: 14,
  },
  noticeText: { color: colors.text, fontSize: 12, lineHeight: 18 },
});
