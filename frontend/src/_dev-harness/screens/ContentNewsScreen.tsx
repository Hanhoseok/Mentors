/**
 * 콘텐츠 동 뉴스 피드 검증 화면 (dev-harness 전용).
 *
 * - GET /api/content/news 결과를 카드로 표시
 * - 신뢰도/전략/감성 배지
 * - 정렬 (latest/reliability/composite) + min_reliability 필터
 * - 검색 박스 → /api/content/news/search (RAG 시맨틱)
 *
 * owner: content 동 (5동) backend — _dev-harness 자유 추가
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { listNews, searchNews } from '@/features/explore/content/api';
import {
  formatPublishedAt,
  pickDisplayTitle,
  RELIABILITY_COLOR_KEY,
  RELIABILITY_LABEL,
  SENTIMENT_LABEL,
  STRATEGY_LABEL,
} from '@/features/explore/content/logic';
import type { NewsArticleResponse, NewsSortBy, SearchHit } from '@/features/explore/content/types';
import { useUserStore } from '@/store/userStore';

const SORT_OPTIONS: { value: NewsSortBy; label: string }[] = [
  { value: 'latest', label: '최신' },
  { value: 'reliability', label: '신뢰도' },
  { value: 'composite', label: '점수' },
];

const MIN_RELIABILITY_OPTIONS = [0, 50, 70, 90];

export function ContentNewsScreen() {
  const accessToken = useUserStore((state) => state.accessToken);
  const [sort, setSort] = useState<NewsSortBy>('latest');
  const [minReliability, setMinReliability] = useState<number>(70);
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const listQuery = useQuery({
    queryKey: ['content-news', { sort, minReliability }],
    queryFn: () =>
      listNews({ sort, min_reliability: minReliability, page: 1, page_size: 30 }),
    enabled: Boolean(accessToken) && !searchQuery,
    retry: 0,
  });

  const searchResultQuery = useQuery({
    queryKey: ['content-news-search', searchQuery],
    queryFn: () => searchNews(searchQuery, 20),
    enabled: Boolean(accessToken) && Boolean(searchQuery),
    retry: 0,
  });

  const onSubmitSearch = () => {
    setSearchQuery(searchInput.trim());
  };

  const onClearSearch = () => {
    setSearchInput('');
    setSearchQuery('');
  };

  if (!accessToken) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.title}>콘텐츠 뉴스</Text>
        <Text style={styles.muted}>로그인이 필요합니다.</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>콘텐츠 뉴스</Text>

        {/* 검색 박스 */}
        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            placeholder="시맨틱 검색 (예: NVIDIA AI chip)"
            value={searchInput}
            onChangeText={setSearchInput}
            onSubmitEditing={onSubmitSearch}
            returnKeyType="search"
          />
          {searchQuery ? (
            <Pressable onPress={onClearSearch} style={styles.searchClearBtn}>
              <Text style={styles.searchClearText}>×</Text>
            </Pressable>
          ) : null}
        </View>

        {/* 필터 — 검색 중일 때는 비활성 */}
        {!searchQuery && (
          <>
            <Text style={styles.sectionLabel}>정렬</Text>
            <View style={styles.chipsRow}>
              {SORT_OPTIONS.map((opt) => (
                <Pressable
                  key={opt.value}
                  onPress={() => setSort(opt.value)}
                  style={[styles.chip, sort === opt.value && styles.chipActive]}
                >
                  <Text style={[styles.chipText, sort === opt.value && styles.chipTextActive]}>
                    {opt.label}
                  </Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.sectionLabel}>최소 신뢰도</Text>
            <View style={styles.chipsRow}>
              {MIN_RELIABILITY_OPTIONS.map((value) => (
                <Pressable
                  key={value}
                  onPress={() => setMinReliability(value)}
                  style={[styles.chip, minReliability === value && styles.chipActive]}
                >
                  <Text
                    style={[styles.chipText, minReliability === value && styles.chipTextActive]}
                  >
                    {value}+
                  </Text>
                </Pressable>
              ))}
            </View>
          </>
        )}

        {/* 결과 영역 */}
        {searchQuery ? (
          <SearchResultsSection
            query={searchQuery}
            isLoading={searchResultQuery.isLoading}
            isError={searchResultQuery.isError}
            results={searchResultQuery.data?.results ?? []}
          />
        ) : (
          <NewsListSection
            isLoading={listQuery.isLoading}
            isError={listQuery.isError}
            articles={listQuery.data?.items ?? []}
            total={listQuery.data?.total ?? 0}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function NewsListSection({
  isLoading,
  isError,
  articles,
  total,
}: {
  isLoading: boolean;
  isError: boolean;
  articles: NewsArticleResponse[];
  total: number;
}) {
  if (isLoading) {
    return <ActivityIndicator style={styles.loading} color={colors.primary} />;
  }
  if (isError) {
    return <Text style={styles.error}>뉴스를 불러오지 못했습니다.</Text>;
  }
  if (articles.length === 0) {
    return (
      <Text style={styles.muted}>조건에 맞는 visible 기사가 없습니다 (최소 신뢰도 낮춰보기).</Text>
    );
  }
  return (
    <>
      <Text style={styles.meta}>{total}건 (페이지 1)</Text>
      {articles.map((article) => (
        <NewsCard key={article.id} article={article} />
      ))}
    </>
  );
}

function SearchResultsSection({
  query,
  isLoading,
  isError,
  results,
}: {
  query: string;
  isLoading: boolean;
  isError: boolean;
  results: SearchHit[];
}) {
  if (isLoading) {
    return <ActivityIndicator style={styles.loading} color={colors.primary} />;
  }
  if (isError) {
    return <Text style={styles.error}>검색 실패 (RAG/Chroma 동작 확인).</Text>;
  }
  if (results.length === 0) {
    return <Text style={styles.muted}>“{query}” 결과 없음.</Text>;
  }
  return (
    <>
      <Text style={styles.meta}>“{query}” → {results.length}건</Text>
      {results.map((hit) => (
        <View key={hit.article_id} style={styles.card}>
          <Text style={styles.cardTitle}>{hit.title}</Text>
          {hit.summary ? <Text style={styles.cardBody}>{hit.summary}</Text> : null}
          <Text style={styles.cardChunk}>“{hit.matched_chunk.slice(0, 200)}…”</Text>
          <Text style={styles.cardFooter}>
            {hit.source_name ?? '출처 미상'} · 점수 {hit.score.toFixed(3)}
          </Text>
        </View>
      ))}
    </>
  );
}

function NewsCard({ article }: { article: NewsArticleResponse }) {
  const title = pickDisplayTitle(article);
  const reliabilityColor = colors[RELIABILITY_COLOR_KEY[article.reliability_level]] ?? colors.muted;
  return (
    <View style={styles.card}>
      {article.image_url ? (
        <Image source={{ uri: article.image_url }} style={styles.cardImage} resizeMode="cover" />
      ) : null}
      <Text style={styles.cardTitle}>{title}</Text>
      {article.summary_ko ? <Text style={styles.cardBody}>{article.summary_ko}</Text> : null}

      <View style={styles.badgesRow}>
        <View style={[styles.badge, { backgroundColor: reliabilityColor }]}>
          <Text style={styles.badgeText}>
            {RELIABILITY_LABEL[article.reliability_level]} ({article.reliability_score})
          </Text>
        </View>
        {article.ai_sentiment ? (
          <View style={styles.badgeMuted}>
            <Text style={styles.badgeTextDark}>
              {SENTIMENT_LABEL[article.ai_sentiment]}
            </Text>
          </View>
        ) : null}
        {article.strategies.map((s) => (
          <View key={s} style={styles.badgeAccent}>
            <Text style={styles.badgeTextDark}>{STRATEGY_LABEL[s]}</Text>
          </View>
        ))}
      </View>

      <Text style={styles.cardFooter}>
        {article.source_name ?? '출처 미상'} · {formatPublishedAt(article.published_at)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 64,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.text,
    marginBottom: 16,
  },
  searchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  searchInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: colors.text,
  },
  searchClearBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.muted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  searchClearText: {
    color: colors.surface,
    fontSize: 18,
    fontWeight: '700',
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.muted,
    marginTop: 8,
    marginBottom: 4,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 12,
    color: colors.text,
  },
  chipTextActive: {
    color: colors.surface,
    fontWeight: '700',
  },
  loading: {
    marginVertical: 30,
  },
  error: {
    color: colors.rose,
    marginTop: 20,
    textAlign: 'center',
  },
  muted: {
    color: colors.muted,
    marginTop: 20,
    textAlign: 'center',
  },
  meta: {
    color: colors.muted,
    fontSize: 12,
    marginBottom: 8,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardImage: {
    width: '100%',
    height: 160,
    borderRadius: 8,
    marginBottom: 10,
    backgroundColor: colors.border,
  },
  cardTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 6,
  },
  cardBody: {
    fontSize: 13,
    color: colors.text,
    marginBottom: 8,
    lineHeight: 18,
  },
  cardChunk: {
    fontSize: 12,
    color: colors.muted,
    fontStyle: 'italic',
    marginBottom: 8,
  },
  badgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeMuted: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: colors.primarySoft,
  },
  badgeAccent: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: colors.accentSoft,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.surface,
  },
  badgeTextDark: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.text,
  },
  cardFooter: {
    fontSize: 11,
    color: colors.muted,
  },
});
