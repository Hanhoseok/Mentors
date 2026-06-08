import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
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
import type { AppStackParamList } from '@/navigation/types';
import { getDailyReport } from '../api';
import { ReportMarkdown } from '../markdown';
import { useInAppNotificationStore } from '@/store/inAppNotificationStore';

type DailyReportDetailRouteProp = RouteProp<AppStackParamList, 'DailyReportDetail'>;

const STRATEGY_LABELS: Record<string, string> = {
  value: '가치투자',
  growth: '성장투자',
  dividend: '배당투자',
  momentum: '모멘텀투자',
};

function formatReportDate(reportDate: string): string {
  const parsed = new Date(reportDate);
  if (Number.isNaN(parsed.getTime())) {
    return reportDate;
  }
  return `${parsed.getFullYear()}년 ${parsed.getMonth() + 1}월 ${parsed.getDate()}일`;
}

export function DailyReportDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const route = useRoute<DailyReportDetailRouteProp>();
  const opener = route.params.opener;
  const preloadedReport = route.params.report ?? null;
  const reportId = route.params.reportId ?? preloadedReport?.id ?? null;
  const addNotification = useInAppNotificationStore((s) => s.addNotification);

  const reportQuery = useQuery({
    queryKey: ['daily-report-detail', reportId],
    queryFn: () => getDailyReport(reportId as number),
    enabled: preloadedReport == null && reportId != null,
  });
  const report = preloadedReport ?? reportQuery.data ?? null;

  // 리포트가 로드되면 인앱 알림 발화 (오늘 첫 진입 시 한 번만)
  useEffect(() => {
    if (!report || report.status !== 'done') return;
    addNotification({
      type: 'daily_report',
      title: '일일 리포트가 도착했어요',
      body: `${STRATEGY_LABELS[report.mentor_strategy] ?? report.mentor_strategy} · ${report.tier} — ${formatReportDate(report.report_date)}`,
      targetScreen: 'DailyReportDetail',
      targetParams: { reportId: report.id },
    });
  }, [report?.id, addNotification]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!report) {
    return (
      <SafeAreaView style={styles.screen}>
        <Header onBack={() => navigation.goBack()} />
        <View style={styles.loadingState}>
          {reportQuery.isError ? (
            <Text style={styles.pendingText}>리포트를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</Text>
          ) : (
            <>
              <ActivityIndicator color={colors.primary} />
              <Text style={styles.pendingText}>불러오는 중...</Text>
            </>
          )}
        </View>
      </SafeAreaView>
    );
  }

  const strategyLabel = STRATEGY_LABELS[report.mentor_strategy] ?? report.mentor_strategy;
  const isReady = report.status === 'ready';

  return (
    <SafeAreaView style={styles.screen}>
      <Header onBack={() => navigation.goBack()} />

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <View style={styles.metaRow}>
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{strategyLabel}</Text>
          </View>
          <View style={[styles.badge, styles.tierBadge]}>
            <Text style={styles.badgeText}>{report.tier}</Text>
          </View>
        </View>

        <Text style={styles.reportDate}>{formatReportDate(report.report_date)}</Text>

        {opener ? <Text style={styles.opener}>{opener}</Text> : null}

        <View style={styles.divider} />

        {isReady && report.body ? (
          <ReportMarkdown body={report.body} />
        ) : (
          <View style={styles.pendingBox}>
            <Text style={styles.pendingText}>리포트를 정리하고 있어요. 잠시 후 다시 확인해 주세요.</Text>
          </View>
        )}

        {report.highlights.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>오늘의 하이라이트</Text>
            <View style={styles.highlightColumn}>
              {report.highlights.map((highlight, index) => {
                const newsId = typeof highlight.news_id === 'number' ? highlight.news_id : null;
                return (
                  <Pressable
                    key={`${highlight.news_id ?? 'highlight'}-${index}`}
                    disabled={newsId === null}
                    onPress={() => {
                      if (newsId !== null) {
                        navigation.navigate('NewsDetail', { newsId });
                      }
                    }}
                    style={({ pressed }) => [
                      styles.highlightCard,
                      pressed && newsId !== null && styles.highlightCardPressed,
                    ]}
                  >
                    <Text style={styles.highlightIndex}>{index + 1}</Text>
                    <Text style={styles.highlightTitle}>{highlight.title ?? '관련 뉴스'}</Text>
                    {newsId !== null ? <Text style={styles.highlightChevron}>›</Text> : null}
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function Header({ onBack }: { onBack: () => void }) {
  return (
    <View style={styles.header}>
      <View style={styles.headerLeft}>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Text style={styles.backBtnText}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>일일 리포트</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  backBtn: {
    padding: 4,
  },
  backBtnText: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.text,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: colors.text,
  },
  loadingState: {
    alignItems: 'center',
    flex: 1,
    gap: 12,
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 32,
  },
  metaRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  tierBadge: {
    backgroundColor: colors.text,
  },
  badgeText: {
    color: colors.surface,
    fontSize: 12,
    fontWeight: '800',
  },
  reportDate: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 12,
  },
  opener: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 22,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 16,
  },
  pendingBox: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 18,
    paddingVertical: 20,
  },
  pendingText: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '800',
    marginTop: 28,
    marginBottom: 12,
  },
  highlightColumn: {
    gap: 10,
  },
  highlightCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  highlightCardPressed: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  highlightChevron: {
    color: colors.muted,
    fontSize: 20,
    fontWeight: '700',
  },
  highlightIndex: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '800',
    width: 16,
  },
  highlightTitle: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    lineHeight: 20,
  },
});
