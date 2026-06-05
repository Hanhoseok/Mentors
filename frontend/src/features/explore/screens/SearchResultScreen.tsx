import { useState, useEffect, useRef } from 'react';
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
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import { searchNews } from '@/features/explore/content/api';
import type { SearchHit } from '@/features/explore/content/types';
import type { AppStackParamList } from '@/navigation/types';
import { TopIconBar } from '@/features/explore/components/TopIconBar';

type RouteProps = RouteProp<AppStackParamList, 'SearchResult'>;

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

export function SearchResultScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const route = useRoute<RouteProps>();
  const { query: initialQuery } = route.params;

  const [inputText, setInputText] = useState(initialQuery);
  const [activeQuery, setActiveQuery] = useState(initialQuery);
  const [results, setResults] = useState<SearchHit[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // activeQuery가 바뀔 때마다 검색 (시맨틱 + 키워드 하이브리드)
  useEffect(() => {
    if (!activeQuery.trim()) return;
    setIsLoading(true);
    setHasSearched(false);
    searchNews(activeQuery.trim(), 20)
      .then((data) => {
        if (mountedRef.current) {
          setResults(data.results);
          setHasSearched(true);
        }
      })
      .catch(() => {
        if (mountedRef.current) {
          setResults([]);
          setHasSearched(true);
        }
      })
      .finally(() => {
        if (mountedRef.current) setIsLoading(false);
      });
  }, [activeQuery]);

  function handleSearch() {
    const q = inputText.trim();
    if (!q) return;
    if (q === activeQuery) {
      // 같은 쿼리 재검색 강제
      setActiveQuery('');
      setTimeout(() => setActiveQuery(q), 0);
    } else {
      setActiveQuery(q);
    }
  }

  function openSummary(item: SearchHit) {
    navigation.navigate('RssArticleSummary', {
      article_id: item.article_id,
      title: item.title,
      url: item.url,
      source_name: item.source_name,
      published_at: item.published_at,
      image_url: item.image_url,
      summary: item.summary,
      content: item.matched_chunk,
    });
  }

  return (
    <SafeAreaView style={styles.screen} edges={['bottom']}>
      {/* 헤더 — 뒤로가기 + 검색창 */}
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <View style={styles.searchBar}>
          <TextInput
            style={styles.searchInput}
            value={inputText}
            onChangeText={setInputText}
            placeholder="검색어를 입력하세요"
            placeholderTextColor="#A4A9A5"
            returnKeyType="search"
            onSubmitEditing={handleSearch}
            autoFocus={false}
          />
          <Pressable
            onPress={handleSearch}
            style={({ pressed }) => [styles.searchBtn, pressed && styles.searchBtnPressed]}
          >
            <Text style={styles.searchBtnText}>검색</Text>
          </Pressable>
        </View>
        <TopIconBar showProfile={false} />
      </View>

      {/* 결과 */}
      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator color={colors.primary} size="large" />
          <Text style={styles.loadingText}>{`"${activeQuery}" 검색 중...`}</Text>
        </View>
      ) : !hasSearched ? null : results.length === 0 ? (
        <View style={styles.centerBox}>
          <Text style={styles.emptyTitle}>검색 결과가 없어요</Text>
          <Text style={styles.emptyDesc}>다른 키워드로 다시 검색해 보세요.</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {/* 결과 수 */}
          <Text style={styles.resultCount}>
            {`"${activeQuery}" 검색 결과 ${results.length}건`}
          </Text>

          {results.map((item, index) => (
            <Pressable
              key={`${item.article_id}-${index}`}
              onPress={() => openSummary(item)}
              style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
            >
              {/* 썸네일 이미지 */}
              {item.image_url ? (
                <Image
                  source={{ uri: item.image_url }}
                  style={styles.thumb}
                  resizeMode="cover"
                />
              ) : null}

              <View style={styles.cardBody}>
                {/* 상단: 출처 뱃지 + 시간 */}
                <View style={styles.cardTop}>
                  <View style={styles.badgeRow}>
                    {item.source_name ? (
                      <View style={styles.sourceBadge}>
                        <Text style={styles.sourceBadgeText}>{item.source_name}</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.timeText}>{formatTime(item.published_at)}</Text>
                </View>

                {/* 제목 */}
                <Text numberOfLines={3} style={styles.title}>
                  {item.title}
                </Text>

                {/* 요약 미리보기 */}
                {item.summary ? (
                  <Text numberOfLines={2} style={styles.summary}>
                    {item.summary}
                  </Text>
                ) : null}

                {/* 링크 힌트 */}
                <Text style={styles.linkHint}>AI 요약 보기 →</Text>
              </View>
            </Pressable>
          ))}
        </ScrollView>
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
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  backBtn: {
    alignItems: 'center',
    flexShrink: 0,
    height: 36,
    justifyContent: 'center',
    width: 32,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
  },
  searchBar: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    flex: 1,
    flexDirection: 'row',
    gap: 8,
    height: 42,
    paddingLeft: 14,
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
  centerBox: {
    alignItems: 'center',
    flex: 1,
    gap: 12,
    justifyContent: 'center',
    padding: 24,
  },
  loadingText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  emptyDesc: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  listContent: {
    alignSelf: 'center',         // 웹에서 가운데 정렬
    gap: 10,
    maxWidth: 800,                // 와이드 스크린에서 카드가 무한정 늘어나지 않도록
    paddingBottom: 32,
    paddingHorizontal: 16,
    paddingTop: 16,
    width: '100%',
  },
  resultCount: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 4,
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    overflow: 'hidden',
  },
  cardPressed: {
    opacity: 0.88,
  },
  thumb: {
    aspectRatio: 16 / 9,         // 원본 비율 유지 (16:9). 카드 가로폭이 800px로
                                 // 캡돼 있으므로 세로는 최대 450px 정도로 떨어짐.
    backgroundColor: '#EDF0ED',
    width: '100%',
  },
  cardBody: {
    gap: 10,
    padding: 16,
  },
  cardTop: {
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
  timeText: {
    color: colors.muted,
    flexShrink: 0,
    fontSize: 11,
  },
  title: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 22,
  },
  summary: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  linkHint: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
});
