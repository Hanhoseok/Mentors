import { useState, useEffect, useCallback, useRef } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';
import { colors } from '@/constants/colors';
import type { AppStackParamList } from '@/navigation/types';
import { fetchLiveTopicNews, listMyKeywords } from '@/features/explore/content/api';
import { getMarketQuotes } from '@/features/explore/market/api';
import type {
  LiveTopicNewsItem,
  UserKeywordResponse,
} from '@/features/explore/content/types';
import type { IndicatorQuote } from '@/features/explore/market/types';

// ── Static fallback data ───────────────────────────────────────────────────────

interface StaticIndicatorData {
  value: string;
  change: string;
  isUp: boolean;
  aiSummary: string;
  points: { x: number; y: number }[];
}

const indicatorFallback: Record<ActiveTab, StaticIndicatorData> = {
  환율: {
    value: '—',
    change: '데이터 로딩 중',
    isUp: true,
    aiSummary:
      '달러/원 환율 최신 데이터를 불러오고 있어요. 미 연준 통화정책 방향과 국내 외환 수급이 단기 환율에 영향을 줍니다.',
    points: [
      { x: 10, y: 100 }, { x: 70, y: 95 }, { x: 130, y: 110 },
      { x: 190, y: 80 }, { x: 250, y: 70 }, { x: 310, y: 50 }, { x: 360, y: 40 },
    ],
  },
  금리: {
    value: '—',
    change: '데이터 로딩 중',
    isUp: false,
    aiSummary:
      '미국 10년물 국채 금리(^TNX)를 기준으로 글로벌 금리 방향을 확인할 수 있어요. 금리 하락은 일반적으로 주식시장에 우호적입니다.',
    points: [
      { x: 10, y: 30 }, { x: 70, y: 30 }, { x: 130, y: 55 },
      { x: 190, y: 55 }, { x: 250, y: 80 }, { x: 310, y: 80 }, { x: 360, y: 95 },
    ],
  },
  코스피: {
    value: '—',
    change: '데이터 로딩 중',
    isUp: false,
    aiSummary:
      '코스피 지수는 한국 대표 우량주 흐름을 종합합니다. 외국인·기관 수급과 글로벌 리스크온/오프 센티먼트가 주요 변수입니다.',
    points: [
      { x: 10, y: 40 }, { x: 70, y: 50 }, { x: 130, y: 45 },
      { x: 190, y: 70 }, { x: 250, y: 65 }, { x: 310, y: 85 }, { x: 360, y: 90 },
    ],
  },
  나스닥: {
    value: '—',
    change: '데이터 로딩 중',
    isUp: true,
    aiSummary:
      '나스닥 지수는 빅테크·AI 섹터의 바로미터입니다. 실적 시즌과 연준 금리 전망이 단기 변동성의 핵심 요인입니다.',
    points: [
      { x: 10, y: 100 }, { x: 70, y: 80 }, { x: 130, y: 75 },
      { x: 190, y: 55 }, { x: 250, y: 40 }, { x: 310, y: 35 }, { x: 360, y: 15 },
    ],
  },
};

type ActiveTab = '환율' | '금리' | '코스피' | '나스닥';

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatIndicatorValue(tab: ActiveTab, value: number): string {
  if (tab === '환율') {
    return (
      value.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
      '원'
    );
  }
  if (tab === '금리') return value.toFixed(2) + '%';
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatIndicatorChange(change: number, changePct: number): string {
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
}

function historyToChartPoints(history: number[]): { x: number; y: number }[] {
  if (history.length < 2) return [];
  const min = Math.min(...history);
  const max = Math.max(...history);
  const range = max - min || 1;
  const W = 350, H = 100, PADX = 10, PADY = 10;
  return history.map((price, i) => ({
    x: PADX + (i / (history.length - 1)) * W,
    y: PADY + (1 - (price - min) / range) * H,
  }));
}

function navigateToLiveSummary(
  navigation: ReturnType<typeof useNavigation<NativeStackNavigationProp<AppStackParamList>>>,
  item: LiveTopicNewsItem,
) {
  // 실시간 토픽 카드는 DB article_id가 없음 — 라우트 파라미터로
  // AI 요약을 직접 전달해서 RssArticleSummaryScreen이 fetch 없이도 렌더되게 함.
  navigation.navigate('RssArticleSummary', {
    title: item.title,
    url: item.url,
    source_name: item.source_name,
    published_at: item.published_at,
    image_url: item.image_url,
    summary: item.summary_ko,
    content: null,
  });
}

function formatTime(publishedAt: string | null): string {
  if (!publishedAt) return '';
  const diff = Date.now() - new Date(publishedAt).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

function buildPath(pts: { x: number; y: number }[]): string {
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
}

function buildAreaPath(pts: { x: number; y: number }[], h: number): string {
  return `${buildPath(pts)} L ${pts[pts.length - 1].x} ${h} L ${pts[0].x} ${h} Z`;
}


// ── Component ──────────────────────────────────────────────────────────────────

export function SearchScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const [activeTab, setActiveTab] = useState<ActiveTab>('환율');
  const [searchQuery, setSearchQuery] = useState('');

  // 주요 뉴스 — 활성 탭(환율/금리/코스피/나스닥) 기반 실시간 RSS + OpenAI 요약
  const [topNews, setTopNews] = useState<LiveTopicNewsItem[]>([]);
  const [isLoadingTop, setIsLoadingTop] = useState(false);

  // 사용자 관심 키워드 (관심사 설정에서 선택된 sub-industry 라벨)
  const [userKeywords, setUserKeywords] = useState<UserKeywordResponse[]>([]);

  // 경제 지수 실시간 데이터
  const [marketQuotes, setMarketQuotes] = useState<Record<string, IndicatorQuote>>({});

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // ── 주요 뉴스: 활성 탭이 바뀔 때마다 실시간 RSS + OpenAI 요약 ────────────
  useEffect(() => {
    let cancelled = false;
    setIsLoadingTop(true);
    setTopNews([]);
    fetchLiveTopicNews(activeTab, 6)
      .then((data) => {
        if (cancelled || !mountedRef.current) return;
        setTopNews(data.items);
      })
      .catch(() => {
        if (cancelled || !mountedRef.current) return;
        setTopNews([]);
      })
      .finally(() => {
        if (cancelled || !mountedRef.current) return;
        setIsLoadingTop(false);
      });
    return () => { cancelled = true; };
  }, [activeTab]);

  // ── 사용자 관심 키워드: 화면 포커스마다 재로드 ────────────────────────────
  // 관심사 설정에서 키워드를 추가/삭제하고 돌아오면 칩이 최신 상태로 보여야 함.
  useFocusEffect(
    useCallback(() => {
      let active = true;
      listMyKeywords()
        .then((data) => { if (active && mountedRef.current) setUserKeywords(data.items); })
        .catch(() => { if (active && mountedRef.current) setUserKeywords([]); });
      return () => { active = false; };
    }, []),
  );

  // ── 경제 지수: 5초 폴링 ───────────────────────────────────────────────────
  useEffect(() => {
    async function refresh() {
      try {
        const data = await getMarketQuotes();
        if (!mountedRef.current) return;
        const map: Record<string, IndicatorQuote> = {};
        for (const q of data.quotes) map[q.name] = q;
        setMarketQuotes(map);
      } catch { /* 오류 시 기존 데이터 유지 */ }
    }
    void refresh();
    const timer = setInterval(() => { void refresh(); }, 5000);
    return () => clearInterval(timer);
  }, []);

  // ── 검색: SearchResultScreen으로 이동 ────────────────────────────────────
  function handleSearch(overrideQuery?: string) {
    const q = (overrideQuery ?? searchQuery).trim();
    if (!q) return;
    navigation.navigate('SearchResult', { query: q });
  }

  function handleKeywordPress(keyword: string) {
    setSearchQuery(keyword);
    handleSearch(keyword);
  }

  // ── 지표 표시값 계산 ──────────────────────────────────────────────────────
  const fallback = indicatorFallback[activeTab];
  const activeQuote = marketQuotes[activeTab];

  const displayValue = activeQuote
    ? formatIndicatorValue(activeTab, activeQuote.value)
    : fallback.value;
  const displayChange = activeQuote
    ? formatIndicatorChange(activeQuote.change, activeQuote.change_pct)
    : fallback.change;
  const isUp = activeQuote ? activeQuote.is_up : fallback.isUp;
  const color = isUp ? colors.primary : colors.rose;
  const chartPoints =
    activeQuote && activeQuote.history.length >= 2
      ? historyToChartPoints(activeQuote.history)
      : fallback.points;

  return (
    <SafeAreaView style={styles.screen}>
      {/* ── 헤더: 검색창 + 아이콘 ── */}
      <View style={styles.header}>
        <View style={styles.searchBar}>
          <TextInput
            placeholder="종목, 뉴스, 경제 용어 검색"
            placeholderTextColor="#A4A9A5"
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
            returnKeyType="search"
            onSubmitEditing={() => handleSearch()}
          />
          <Pressable
            onPress={() => handleSearch()}
            style={({ pressed }) => [styles.searchBtn, pressed && styles.searchBtnPressed]}
          >
            <Text style={styles.searchBtnText}>검색</Text>
          </Pressable>
        </View>

        <View style={styles.iconRow}>
          <Pressable
            onPress={() => Alert.alert('알림', '새로운 알림이 없습니다.')}
            style={styles.iconBtn}
          >
            <Text style={styles.iconText}>🔔</Text>
          </Pressable>
          <Pressable
            onPress={() => Alert.alert('스크랩', '스크랩 페이지 개발 중입니다.')}
            style={styles.iconBtn}
          >
            <Text style={styles.iconText}>📌</Text>
          </Pressable>
          <Pressable onPress={() => navigation.navigate('Settings')} style={styles.iconBtn}>
            <Text style={styles.iconText}>👤</Text>
          </Pressable>
        </View>
      </View>

      {/* ── 사용자 키워드 패널 — 검색창 바로 아래 상시 노출 ── */}
      <View style={styles.keywordPanel}>
        <Text style={styles.keywordPanelTitle}>내 관심 키워드</Text>
        {userKeywords.length === 0 ? (
          <Pressable
            onPress={() => navigation.navigate('InterestSettings')}
            style={({ pressed }) => [
              styles.keywordPanelEmptyBox,
              pressed && styles.userKeywordChipPressed,
            ]}
          >
            <Text style={styles.keywordPanelEmpty}>
              관심사 설정에서 키워드를 추가해 보세요 →
            </Text>
          </Pressable>
        ) : (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
            contentContainerStyle={styles.keywordPanelRow}
          >
            {userKeywords.map((uk) => (
              <Pressable
                key={uk.id}
                onPress={() => handleKeywordPress(uk.keyword)}
                style={({ pressed }) => [
                  styles.userKeywordChip,
                  pressed && styles.userKeywordChipPressed,
                ]}
              >
                <Text style={styles.userKeywordChipText}>{uk.keyword}</Text>
              </Pressable>
            ))}
          </ScrollView>
        )}
      </View>

      {/* ── 탭 바 ── */}
      <View style={styles.tabBar}>
        {(['환율', '금리', '코스피', '나스닥'] as ActiveTab[]).map((tab) => (
          <Pressable
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={[styles.tabItem, activeTab === tab && styles.tabItemActive]}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* ── 메인 스크롤 ── */}
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>

        {/* 지표 차트 카드 */}
        <View style={styles.chartCard}>
          <View style={styles.chartValueRow}>
            <Text style={styles.metricValue}>{displayValue}</Text>
            {activeQuote ? (
              <View style={styles.liveTag}>
                <Text style={styles.liveTagText}>LIVE</Text>
              </View>
            ) : null}
          </View>
          <Text style={[styles.metricChange, { color }]}>{displayChange}</Text>

          <View style={styles.chartContainer}>
            <Svg width="100%" height="100%" viewBox="0 0 370 120">
              <Defs>
                <LinearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0%" stopColor={color} stopOpacity="0.2" />
                  <Stop offset="100%" stopColor={color} stopOpacity="0.0" />
                </LinearGradient>
              </Defs>
              {chartPoints.length >= 2 ? (
                <>
                  <Path d={buildAreaPath(chartPoints, 120)} fill="url(#areaGrad)" />
                  <Path
                    d={buildPath(chartPoints)}
                    fill="none"
                    stroke={color}
                    strokeWidth="2.5"
                  />
                </>
              ) : null}
            </Svg>
          </View>

          <View style={styles.timeRow}>
            <Text style={styles.timeText}>5일 전</Text>
            <Text style={styles.timeText}>3일 전</Text>
            <Text style={styles.timeText}>전일</Text>
            <Text style={styles.timeText}>현재</Text>
          </View>
        </View>

        {/* AI 요약 카드 */}
        <View style={styles.aiCard}>
          <View style={styles.aiBadge}>
            <Text style={styles.aiBadgeText}>AI</Text>
          </View>
          <Text style={styles.aiText}>{fallback.aiSummary}</Text>
        </View>

        {/* 주요 뉴스 섹션 — 활성 탭(환율/금리/코스피/나스닥) 기반 */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>{activeTab} 주요 뉴스</Text>
          {isLoadingTop ? <ActivityIndicator color={colors.primary} size="small" /> : null}
        </View>

        {isLoadingTop ? (
          <View style={styles.loadingBox}>
            <ActivityIndicator color={colors.primary} />
            <Text style={styles.loadingText}>
              {activeTab} 관련 뉴스를 가져와 AI 요약 중...
            </Text>
          </View>
        ) : topNews.length > 0 ? (
          <View style={styles.newsList}>
            {topNews.map((item, idx) => (
              <Pressable
                key={`${item.url}-${idx}`}
                onPress={() => navigateToLiveSummary(navigation, item)}
                style={({ pressed }) => [styles.newsCard, pressed && styles.pressed]}
              >
                {item.image_url ? (
                  <Image
                    source={{ uri: item.image_url }}
                    style={styles.newsThumb}
                    resizeMode="cover"
                  />
                ) : null}
                <View style={styles.newsCardBody}>
                  <View style={styles.newsCardTop}>
                    <View style={styles.badgeRow}>
                      {item.source_name ? (
                        <View style={styles.sourceBadge}>
                          <Text style={styles.sourceBadgeText}>{item.source_name}</Text>
                        </View>
                      ) : null}
                    </View>
                    <Text style={styles.newsTime}>{formatTime(item.published_at)}</Text>
                  </View>
                  <Text numberOfLines={2} style={styles.newsTitle}>
                    {item.title}
                  </Text>
                  {item.summary_ko ? (
                    <Text numberOfLines={3} style={styles.newsSummary}>
                      {item.summary_ko}
                    </Text>
                  ) : null}
                  <Text style={styles.newsLink}>AI 요약 보기 →</Text>
                </View>
              </Pressable>
            ))}
          </View>
        ) : (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyTitle}>
              {activeTab} 관련 뉴스를 가져오지 못했어요
            </Text>
            <Text style={styles.emptyDesc}>
              네트워크 상태를 확인하고 잠시 후 다시 시도해 주세요.
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'space-between',
    paddingBottom: 8,
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  searchBar: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    height: 44,
    paddingLeft: 16,
    paddingRight: 6,
  },
  searchInput: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
  },
  searchBtn: {
    backgroundColor: colors.primary,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  searchBtnPressed: {
    opacity: 0.8,
  },
  searchBtnText: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '700',
  },
  iconRow: {
    flexDirection: 'row',
    gap: 8,
  },
  iconBtn: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  iconText: {
    fontSize: 18,
  },
  // ── 사용자 키워드 패널 ──
  keywordPanel: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    gap: 8,
    paddingBottom: 12,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  keywordPanelTitle: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  keywordPanelEmpty: {
    color: colors.muted,
    fontSize: 13,
  },
  keywordPanelEmptyBox: {
    paddingVertical: 4,
  },
  keywordPanelRow: {
    alignItems: 'center',
    gap: 8,
    paddingRight: 16,
  },
  userKeywordChip: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  userKeywordChipPressed: {
    opacity: 0.8,
  },
  userKeywordChipText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
  // ──
  tabBar: {
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
  },
  tabItem: {
    alignItems: 'center',
    flex: 1,
    paddingVertical: 14,
  },
  tabItemActive: {
    borderBottomWidth: 3,
    borderColor: colors.primary,
  },
  tabText: {
    color: colors.muted,
    fontSize: 15,
    fontWeight: '600',
  },
  tabTextActive: {
    color: colors.primary,
    fontWeight: '800',
  },
  content: {
    paddingBottom: 24,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  chartCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    elevation: 2,
    marginBottom: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
  },
  chartValueRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  metricValue: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '800',
  },
  liveTag: {
    backgroundColor: colors.rose,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  liveTagText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  metricChange: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 16,
    marginTop: 4,
  },
  chartContainer: {
    height: 120,
    width: '100%',
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
    paddingHorizontal: 8,
  },
  timeText: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '500',
  },
  aiCard: {
    backgroundColor: colors.primarySoft,
    borderRadius: 16,
    gap: 8,
    marginBottom: 24,
    padding: 16,
  },
  aiBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  aiBadgeText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '800',
  },
  aiText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 20,
  },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  loadingBox: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 10,
    justifyContent: 'center',
    minHeight: 100,
  },
  loadingText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
  },
  newsList: {
    gap: 10,
  },
  newsCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  newsThumb: {
    aspectRatio: 16 / 9,         // 원본 비율 유지 — 잘림 없이 16:9
    backgroundColor: '#EDF0ED',
    width: '100%',
  },
  newsCardBody: {
    gap: 8,
    padding: 16,
  },
  newsCardTop: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
  },
  badgeRow: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  sourceBadge: {
    backgroundColor: '#3E654F',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  sourceBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  newsTime: {
    color: colors.muted,
    flexShrink: 0,
    fontSize: 11,
  },
  newsTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 21,
  },
  newsSummary: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  keywordRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 5,
  },
  keywordChip: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderRadius: 20,
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  keywordChipText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '600',
  },
  newsLink: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 2,
  },
  emptyBox: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 8,
    justifyContent: 'center',
    minHeight: 120,
    padding: 24,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: '800',
  },
  emptyDesc: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.9,
  },
});
