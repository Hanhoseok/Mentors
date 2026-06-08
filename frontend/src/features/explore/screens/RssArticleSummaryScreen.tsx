import { useState, useEffect, useRef, useCallback } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute, useFocusEffect, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import { IconLabel } from '@/components/AppIcon';
import { getNewsDetail, listMyScraps, searchNews } from '@/features/explore/content/api';
import type { NewsArticleResponse, SearchHit } from '@/features/explore/content/types';
import type { AppStackParamList } from '@/navigation/types';
import {
  ScrapFolderPicker,
  type ScrapDraft,
} from '@/features/scrap/components/ScrapFolderPicker';
import { openInAppBrowser } from '@/utils';

type RouteProps = RouteProp<AppStackParamList, 'RssArticleSummary'>;
type RssNavigation = NativeStackNavigationProp<AppStackParamList>;

function formatTime(publishedAt: string | null): string {
  if (!publishedAt) return '';
  const diff = Date.now() - new Date(publishedAt).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  const days = Math.floor(hours / 24);
  return `${days}일 전`;
}

const SENTIMENT_MAP: Record<string, { label: string; bg: string; text: string }> = {
  positive: { label: '긍정적', bg: '#D6F5E3', text: '#1A7A45' },
  neutral:  { label: '중립',   bg: '#EFEFEF', text: '#555' },
  negative: { label: '부정적', bg: '#FFE5E5', text: '#C0392B' },
};

const RELEVANCE_MAP: Record<string, { label: string; bg: string; text: string }> = {
  high:   { label: '관련도 높음', bg: '#FFF0DA', text: '#B05A00' },
  medium: { label: '관련도 보통', bg: '#EFEFEF', text: '#555' },
  low:    { label: '관련도 낮음', bg: '#F0F0F0', text: '#888' },
};

const STRATEGY_MAP: Record<string, string> = {
  value:    '가치주',
  growth:   '성장주',
  dividend: '배당주',
  momentum: '모멘텀',
};

/** 본문 텍스트를 카드뉴스용 요약(3~5문장)으로 압축. */
function buildBodyExcerpt(text: string | null | undefined, maxChars = 480): string | null {
  if (!text) return null;
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return null;
  if (cleaned.length <= maxChars) return cleaned;
  // 마지막 문장부호 부근에서 자르기
  const slice = cleaned.slice(0, maxChars);
  const lastStop = Math.max(
    slice.lastIndexOf('.'),
    slice.lastIndexOf('!'),
    slice.lastIndexOf('?'),
    slice.lastIndexOf('다.'),
    slice.lastIndexOf('요.'),
  );
  if (lastStop > maxChars * 0.6) return slice.slice(0, lastStop + 1).trim();
  return slice.trim() + '…';
}

export function RssArticleSummaryScreen() {
  const navigation = useNavigation<RssNavigation>();
  const route = useRoute<RouteProps>();
  const insets = useSafeAreaInsets();
  const {
    title,
    url,
    source_name,
    published_at,
    article_id,
    image_url: initialImage,
    summary: initialSummary,
    content: initialContent,
  } = route.params;

  const [detail, setDetail] = useState<NewsArticleResponse | null>(null);
  const [isLoading, setIsLoading] = useState(article_id !== undefined);
  const [error, setError] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isScrapped, setIsScrapped] = useState(false);
  const [related, setRelated] = useState<SearchHit[]>([]);
  const [reloadTick, setReloadTick] = useState(0);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (article_id === undefined) {
      setIsLoading(false);
      // article_id 없이도 제목으로 관련 기사 검색
      const query = title.slice(0, 80);
      if (query) {
        searchNews(query, 6)
          .then((res) => {
            if (mountedRef.current) setRelated(res.results.slice(0, 5));
          })
          .catch(() => {});
      }
      return;
    }
    setIsLoading(true);
    setError(false);
    getNewsDetail(article_id)
      .then(async (data) => {
        if (!mountedRef.current) return;
        setDetail(data);
        // 관련 기사: 제목 기반 시맨틱 검색
        const query = (data.display_title ?? data.title_original ?? title).slice(0, 80);
        if (query) {
          searchNews(query, 6)
            .then((res) => {
              if (mountedRef.current) {
                setRelated(res.results.filter((r) => r.article_id !== article_id).slice(0, 5));
              }
            })
            .catch(() => {});
        }
      })
      .catch(() => { if (mountedRef.current) setError(true); })
      .finally(() => { if (mountedRef.current) setIsLoading(false); });
  }, [article_id, title, reloadTick]);

  // 스크랩 여부 확인 — article_id 또는 url로 매칭. 화면 포커스마다 재확인하여
  // 스크랩 후 나갔다 들어와도 '저장됨' 상태가 유지되도록 한다.
  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      listMyScraps({ limit: 200 })
        .then((scraps) => {
          if (cancelled) return;
          const found = scraps.some(
            (s) =>
              (article_id !== undefined && s.article_id === article_id) ||
              (!!url && s.url === url),
          );
          setIsScrapped(found);
        })
        .catch(() => { /* 조회 실패 시 현재 상태 유지 */ });
      return () => { cancelled = true; };
    }, [article_id, url]),
  );

  function openOriginal() {
    if (Platform.OS === 'web') {
      void openInAppBrowser(url);
      return;
    }
    navigation.navigate('InAppBrowser', { url, title: displayTitle });
  }

  // 표시 데이터 — detail 우선, 없으면 라우트 파라미터 fallback
  const displayTitle =
    detail?.display_title ?? detail?.title_original ?? title;
  const aiSummary = detail?.display_summary ?? detail?.summary_ko ?? initialSummary ?? null;
  const bodySource =
    detail?.content_translated ?? detail?.content ?? initialContent ?? null;
  const bodyExcerpt = buildBodyExcerpt(bodySource);
  const imageUrl = imageError
    ? null
    : (detail?.image_url ?? initialImage ?? null);
  const timeLabel = formatTime(published_at);
  const sentiment = detail?.ai_sentiment ?? null;
  const relevance = detail?.ai_investment_relevance ?? null;
  const strategies = detail?.strategies ?? [];
  const keywords = detail?.keywords ?? [];
  const reliabilityScore = detail?.reliability_score ?? null;

  const sentimentInfo = sentiment ? SENTIMENT_MAP[sentiment] : null;
  const relevanceInfo = relevance ? RELEVANCE_MAP[relevance] : null;
  const showAnalysis = !!detail && !isLoading;

  // AI 처리 상태 — 요약이 '준비 중'인지(pending/processing) vs 영영 제공 안 되는지
  // (skipped/failed)를 구분해서 정직하게 안내한다.
  const aiStatus = detail?.ai_processing_status ?? null;
  const aiPending = aiStatus === 'pending' || aiStatus === 'processing';

  // 스크랩 폴더 저장용 기사 스냅샷
  const scrapCategory =
    (strategies.length > 0 ? STRATEGY_MAP[strategies[0]] ?? strategies[0] : null) ??
    source_name ??
    null;
  const scrapDraft: ScrapDraft = {
    article_id: article_id ?? null,
    title: displayTitle,
    url,
    image_url: imageUrl,
    summary: aiSummary,
    source_name: source_name,
    category: scrapCategory,
    published_at: published_at,
  };

  return (
    <SafeAreaView style={styles.screen} edges={['left', 'right', 'bottom']}>
      {/* 헤더 */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>AI 요약</Text>
        <View style={styles.headerRight}>
          {isScrapped ? (
            <View style={styles.savedBadge}>
              <IconLabel
                color={colors.primary}
                icon="check-circle"
                iconColor={colors.primary}
                iconSize={14}
                label="저장됨"
                textStyle={styles.savedBadgeText}
              />
            </View>
          ) : null}
          <Pressable
            onPress={() => setPickerOpen(true)}
            style={({ pressed }) => [styles.scrapBtn, pressed && styles.pressed]}
          >
            <IconLabel
              icon="bookmark"
              iconColor={colors.text}
              iconSize={15}
              label="스크랩 추가"
              textStyle={styles.scrapBtnText}
            />
          </Pressable>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* 대표 이미지 */}
        {imageUrl ? (
          <View style={styles.imageWrapper}>
            <Image
              source={{ uri: imageUrl }}
              style={styles.image}
              resizeMode="cover"
              onError={() => setImageError(true)}
            />
            {source_name ? (
              <View style={styles.imageSourceBadge}>
                <Text style={styles.imageSourceText}>{source_name}</Text>
              </View>
            ) : null}
          </View>
        ) : isLoading ? (
          <View style={[styles.imageWrapper, styles.imagePlaceholder]}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : (
          source_name ? (
            <View style={styles.noImageSourceRow}>
              <View style={styles.sourceBadge}>
                <Text style={styles.sourceBadgeText}>{source_name}</Text>
              </View>
              {timeLabel ? <Text style={styles.metaTime}>{timeLabel}</Text> : null}
            </View>
          ) : null
        )}

        {/* 이미지 아래 메타 */}
        {imageUrl ? (
          <View style={styles.metaRowAfterImage}>
            {source_name ? (
              <View style={styles.sourceBadge}>
                <Text style={styles.sourceBadgeText}>{source_name}</Text>
              </View>
            ) : null}
            {timeLabel ? <Text style={styles.metaTime}>{timeLabel}</Text> : null}
          </View>
        ) : null}

        {/* 기사 제목 */}
        <Text style={styles.articleTitle}>{displayTitle}</Text>

        {/* ── AI 분석 배지 행 ── */}
        {showAnalysis ? (
          <View style={styles.badgeRow}>
            {reliabilityScore != null ? (
              <View style={styles.reliabilityBadge}>
                <Text style={styles.reliabilityLabel}>신뢰도</Text>
                <Text style={styles.reliabilityValue}>{reliabilityScore}</Text>
                <View style={styles.reliabilityBarBg}>
                  <View
                    style={[
                      styles.reliabilityBarFill,
                      {
                        width: `${reliabilityScore}%` as `${number}%`,
                        backgroundColor:
                          reliabilityScore >= 70
                            ? colors.primary
                            : reliabilityScore >= 40
                            ? '#E6A817'
                            : '#C0392B',
                      },
                    ]}
                  />
                </View>
              </View>
            ) : null}

            {sentimentInfo ? (
              <View style={[styles.chip, { backgroundColor: sentimentInfo.bg }]}>
                <Text style={[styles.chipText, { color: sentimentInfo.text }]}>
                  {sentimentInfo.label}
                </Text>
              </View>
            ) : null}

            {relevanceInfo ? (
              <View style={[styles.chip, { backgroundColor: relevanceInfo.bg }]}>
                <Text style={[styles.chipText, { color: relevanceInfo.text }]}>
                  {relevanceInfo.label}
                </Text>
              </View>
            ) : null}
          </View>
        ) : null}

        {/* 투자 전략 */}
        {showAnalysis && strategies.length > 0 ? (
          <View style={styles.strategyRow}>
            <Text style={styles.sectionLabel}>투자 전략</Text>
            <View style={styles.chipRow}>
              {strategies.map((s) => (
                <View key={s} style={styles.strategyChip}>
                  <Text style={styles.strategyChipText}>
                    {STRATEGY_MAP[s] ?? s}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}

        {/* 키워드 */}
        {showAnalysis && keywords.length > 0 ? (
          <View style={styles.keywordRow}>
            <Text style={styles.sectionLabel}>키워드</Text>
            <View style={styles.chipRow}>
              {keywords.map((kw, i) => (
                <View key={`${kw}-${i}`} style={styles.keywordChip}>
                  <Text style={styles.keywordChipText}>{kw}</Text>
                </View>
              ))}
            </View>
          </View>
        ) : null}

        <View style={styles.divider} />

        {/* AI 요약 섹션 */}
        <View style={styles.summaryCard}>
          <View style={styles.summaryHeader}>
            <View style={styles.aiBadge}>
              <Text style={styles.aiBadgeText}>AI 요약</Text>
            </View>
            {isLoading ? (
              <View style={styles.loadingRow}>
                <ActivityIndicator color={colors.primary} size="small" />
                <Text style={styles.loadingText}>AI가 기사를 읽고 있어요...</Text>
              </View>
            ) : null}
          </View>

          {isLoading ? (
            <View style={styles.skeletonWrap}>
              <View style={[styles.skeletonLine, { width: '100%' }]} />
              <View style={[styles.skeletonLine, { width: '92%' }]} />
              <View style={[styles.skeletonLine, { width: '96%' }]} />
              <View style={[styles.skeletonLine, { width: '80%' }]} />
            </View>
          ) : aiSummary ? (
            <Text style={styles.summaryText}>{aiSummary}</Text>
          ) : error ? (
            <Text style={styles.errorText}>
              요약을 불러오지 못했어요. 원문을 직접 확인해 주세요.
            </Text>
          ) : aiPending ? (
            <View style={styles.statusBox}>
              <Text style={styles.statusText}>
                AI가 이 기사의 요약을 준비하고 있어요. 잠시 후 다시 확인해 주세요.
              </Text>
              <Pressable
                onPress={() => setReloadTick((t) => t + 1)}
                style={({ pressed }) => [styles.recheckBtn, pressed && styles.pressed]}
              >
                <Text style={styles.recheckBtnText}>다시 확인</Text>
              </Pressable>
            </View>
          ) : (
            <Text style={styles.statusMutedText}>
              이 뉴스는 신뢰도가 낮아 AI 요약을 제공하지 않아요. 아래 원문에서 내용을 확인해 주세요.
            </Text>
          )}
        </View>

        {/* 본문 요약(기사 발췌) — AI 요약과 별도로 노출 */}
        {bodyExcerpt ? (
          <View style={styles.bodyCard}>
            <View style={styles.bodyHeader}>
              <View style={styles.bodyBadge}>
                <Text style={styles.bodyBadgeText}>본문 요약</Text>
              </View>
            </View>
            <Text style={styles.bodyText}>{bodyExcerpt}</Text>
          </View>
        ) : null}

        {/* 원문 보기 버튼 */}
        <Pressable
          onPress={openOriginal}
          style={({ pressed }) => [styles.originalBtn, pressed && styles.pressed]}
        >
          <IconLabel
            color={colors.primary}
            icon="open-in-new"
            iconColor={colors.primary}
            iconSize={16}
            label="원문 기사 보기"
            textStyle={styles.originalBtnText}
          />
        </Pressable>

        {/* 관련 기사 — SearchScreen 카드 스타일 */}
        {related.length > 0 ? (
          <>
            <Text style={styles.relatedSectionTitle}>관련 기사</Text>
            <View style={styles.relatedList}>
              {related.map((item) => (
                <Pressable
                  key={item.article_id}
                  onPress={() =>
                    navigation.push('NewsDetail', { newsId: item.article_id })
                  }
                  style={({ pressed }) => [styles.relatedCard, pressed && styles.pressed]}
                >
                  {item.image_url ? (
                    <Image
                      source={{ uri: item.image_url }}
                      style={styles.relatedThumb}
                      resizeMode="cover"
                    />
                  ) : null}
                  <View style={styles.relatedCardBody}>
                    <View style={styles.relatedCardTop}>
                      <View style={styles.relatedBadgeRow}>
                        {item.source_name ? (
                          <View style={styles.relatedBadge}>
                            <Text style={styles.relatedBadgeText}>{item.source_name}</Text>
                          </View>
                        ) : null}
                      </View>
                      <Text style={styles.relatedTime}>{formatTime(item.published_at)}</Text>
                    </View>
                    <Text numberOfLines={2} style={styles.relatedTitle}>
                      {item.title}
                    </Text>
                    {item.summary ? (
                      <Text numberOfLines={3} style={styles.relatedSummary}>
                        {item.summary}
                      </Text>
                    ) : null}
                    <Text style={styles.relatedLink}>AI 요약 보기 →</Text>
                  </View>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>

      <ScrapFolderPicker
        visible={pickerOpen}
        draft={scrapDraft}
        onClose={() => setPickerOpen(false)}
        onScrapped={(folderName) => {
          setIsScrapped(true);
          Alert.alert('스크랩 완료', `'${folderName}' 폴더에 저장했어요.`);
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.background,
    flex: 1,
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    minHeight: 56,
    paddingBottom: 12,
    paddingHorizontal: 16,
  },
  backBtn: {
    alignItems: 'center',
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
  },
  headerTitle: {
    color: colors.text,
    flexShrink: 1,
    fontSize: 17,
    fontWeight: '800',
    marginLeft: 4,
  },
  headerRight: {
    alignItems: 'center',
    flexDirection: 'row',
    flex: 1,
    gap: 8,
    justifyContent: 'flex-end',
  },
  scrapBtn: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 99,
    flexDirection: 'row',
    flexShrink: 0,
    height: 40,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  scrapBtnText: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '800',
  },
  content: {
    alignSelf: 'center',         // 웹 와이드 스크린 가운데 정렬
    maxWidth: 800,
    paddingBottom: 40,
    paddingHorizontal: 16,
    paddingTop: 16,
    width: '100%',
  },
  imageWrapper: {
    aspectRatio: 16 / 9,         // 원본 비율 유지
    borderRadius: 20,
    marginBottom: 12,
    overflow: 'hidden',
    width: '100%',
  },
  image: {
    height: '100%',
    width: '100%',
  },
  imagePlaceholder: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    justifyContent: 'center',
  },
  imageSourceBadge: {
    backgroundColor: 'rgba(0,0,0,0.55)',
    borderRadius: 6,
    bottom: 12,
    left: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    position: 'absolute',
  },
  imageSourceText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '700',
  },
  noImageSourceRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  metaRowAfterImage: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginBottom: 10,
  },
  sourceBadge: {
    backgroundColor: '#3E654F',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  sourceBadgeText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '700',
  },
  metaTime: {
    color: colors.muted,
    fontSize: 12,
  },
  articleTitle: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '800',
    lineHeight: 28,
    marginBottom: 14,
  },
  // ── AI 분석 배지 ──
  badgeRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  reliabilityBadge: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  reliabilityLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '600',
  },
  reliabilityValue: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '800',
  },
  reliabilityBarBg: {
    backgroundColor: colors.border,
    borderRadius: 3,
    height: 6,
    overflow: 'hidden',
    width: 48,
  },
  reliabilityBarFill: {
    borderRadius: 3,
    height: '100%',
  },
  chip: {
    borderRadius: 20,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '700',
  },
  sectionLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 6,
  },
  strategyRow: {
    marginBottom: 10,
  },
  chipRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  strategyChip: {
    backgroundColor: '#E8F4FD',
    borderColor: '#7BB8E8',
    borderRadius: 20,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  strategyChipText: {
    color: '#1A5F8A',
    fontSize: 12,
    fontWeight: '700',
  },
  keywordRow: {
    marginBottom: 12,
  },
  keywordChip: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderRadius: 20,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  keywordChipText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
  },
  divider: {
    backgroundColor: colors.border,
    height: 1,
    marginBottom: 16,
  },
  summaryCard: {
    backgroundColor: '#F0F7F4',
    borderColor: '#D8ECE2',
    borderRadius: 16,
    borderWidth: 1,
    gap: 12,
    marginBottom: 16,
    padding: 18,
  },
  summaryHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  aiBadge: {
    backgroundColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  aiBadgeText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '800',
  },
  loadingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
  },
  loadingText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  skeletonWrap: {
    gap: 10,
    paddingTop: 4,
  },
  skeletonLine: {
    backgroundColor: '#D8ECE2',
    borderRadius: 6,
    height: 14,
  },
  summaryText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '500',
    lineHeight: 24,
  },
  errorText: {
    color: colors.rose,
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 20,
  },
  statusBox: {
    gap: 12,
  },
  statusText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 21,
  },
  statusMutedText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '500',
    lineHeight: 21,
  },
  recheckBtn: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 99,
    paddingHorizontal: 18,
    paddingVertical: 9,
  },
  recheckBtnText: {
    color: colors.surface,
    fontSize: 13,
    fontWeight: '800',
  },
  bodyCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 10,
    marginBottom: 20,
    padding: 18,
  },
  bodyHeader: {
    alignItems: 'center',
    flexDirection: 'row',
  },
  bodyBadge: {
    backgroundColor: '#3E654F',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  bodyBadgeText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '800',
  },
  bodyText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '400',
    lineHeight: 22,
  },
  originalBtn: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.primary,
    borderRadius: 99,
    borderWidth: 1.5,
    height: 50,
    justifyContent: 'center',
    marginBottom: 32,
  },
  originalBtnText: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '700',
  },
  // ── 스크랩 '저장됨' 배지 (스크랩 추가 버튼 왼쪽) ──
  savedBadge: {
    alignItems: 'center',
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderRadius: 99,
    borderWidth: 1,
    flexDirection: 'row',
    flexShrink: 0,
    height: 40,
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  savedBadgeText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '800',
  },
  // ── 관련 기사 (SearchScreen 카드 스타일) ──
  relatedSectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 12,
    marginTop: 8,
  },
  relatedList: {
    gap: 10,
  },
  relatedCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  relatedThumb: {
    aspectRatio: 16 / 9,
    backgroundColor: '#EDF0ED',
    width: '100%',
  },
  relatedCardBody: {
    gap: 8,
    padding: 14,
  },
  relatedCardTop: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  relatedBadgeRow: {
    alignItems: 'center',
    flex: 1,
    flexDirection: 'row',
    gap: 6,
  },
  relatedBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#3E654F',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  relatedBadgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '700',
  },
  relatedTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 21,
  },
  relatedSummary: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  relatedTime: {
    color: colors.muted,
    flexShrink: 0,
    fontSize: 11,
  },
  relatedLink: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    marginTop: 2,
  },
  pressed: {
    opacity: 0.85,
  },
});
