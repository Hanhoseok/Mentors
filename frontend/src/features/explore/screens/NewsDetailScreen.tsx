import { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  Pressable,
  ScrollView,
  Alert,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import { IconLabel } from '@/components/AppIcon';
import type { AppStackParamList } from '@/navigation/types';
import { getNewsDetail, listMyScraps, searchNews } from '@/features/explore/content/api';
import type { NewsArticleResponse, SearchHit } from '@/features/explore/content/types';
import {
  ScrapFolderPicker,
  type ScrapDraft,
} from '@/features/scrap/components/ScrapFolderPicker';
import { openInAppBrowser } from '@/utils';

type NewsDetailRouteProp = RouteProp<AppStackParamList, 'NewsDetail'>;

function formatPublishedAt(publishedAt: string | null): string {
  if (!publishedAt) return '';
  const diff = Date.now() - new Date(publishedAt).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function NewsDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const route = useRoute<NewsDetailRouteProp>();
  const insets = useSafeAreaInsets();
  const { newsId } = route.params;

  const [article, setArticle] = useState<NewsArticleResponse | null>(null);
  const [related, setRelated] = useState<SearchHit[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isScrapped, setIsScrapped] = useState(false);

  useEffect(() => {
    let ignore = false;
    setIsLoading(true);

    getNewsDetail(newsId)
      .then(async (detail) => {
        if (ignore) return;
        setArticle(detail);
        // 스크랩 여부 확인
        try {
          const scraps = await listMyScraps({ limit: 200 });
          if (!ignore) {
            setIsScrapped(scraps.some((s) => s.article_id === newsId));
          }
        } catch { /* 조회 실패 시 false 유지 */ }
        // 관련 뉴스: 제목 기반 시맨틱 검색
        const query = (detail.display_title ?? detail.title_original ?? '').slice(0, 80);
        if (query) {
          searchNews(query, 6)
            .then((res) => {
              if (!ignore) {
                setRelated(res.results.filter((r) => r.article_id !== newsId).slice(0, 5));
              }
            })
            .catch(() => { /* 조용히 실패 */ });
        }
      })
      .catch(() => {
        if (!ignore) setArticle(null);
      })
      .finally(() => {
        if (!ignore) setIsLoading(false);
      });

    return () => { ignore = true; };
  }, [newsId]);

  const handleOriginalPress = () => {
    if (!article?.original_url) {
      Alert.alert('원본 기사', '원본 URL이 없습니다.');
      return;
    }
    if (Platform.OS === 'web') {
      void openInAppBrowser(article.original_url);
      return;
    }
    navigation.navigate('InAppBrowser', {
      url: article.original_url,
      title: article.display_title ?? article.title_original,
    });
  };

  const scrapDraft: ScrapDraft | null = article
    ? {
        article_id: article.id,
        title: article.display_title ?? article.title_original,
        url: article.original_url,
        image_url: article.image_url,
        summary: article.display_summary ?? article.summary_ko,
        source_name: article.source_name,
        category: article.strategies[0] ?? article.source_name ?? null,
        published_at: article.published_at,
      }
    : null;

  return (
    <SafeAreaView style={styles.screen} edges={['left', 'right', 'bottom']}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 12 }]}>
        <View style={styles.headerLeft}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backBtnText}>←</Text>
          </Pressable>
          <Text style={styles.headerTitle}>뉴스 상세</Text>
        </View>

        <Pressable
          onPress={() => setPickerOpen(true)}
          disabled={!scrapDraft}
          style={({ pressed }) => [
            styles.scrapBtn,
            isScrapped && styles.scrapBtnSaved,
            !scrapDraft && styles.scrapBtnDisabled,
            pressed && styles.pressed,
          ]}
        >
          <IconLabel
            color={isScrapped ? colors.primary : colors.text}
            icon={isScrapped ? 'check-circle' : 'bookmark'}
            iconColor={isScrapped ? colors.primary : colors.text}
            iconSize={15}
            label={isScrapped ? '저장됨' : '스크랩'}
            textStyle={[styles.scrapBtnText, isScrapped && styles.scrapBtnTextSaved]}
          />
        </Pressable>
      </View>

      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator color={colors.primary} />
          <Text style={styles.loadingText}>기사를 불러오는 중...</Text>
        </View>
      ) : !article ? (
        <View style={styles.loadingContainer}>
          <Text style={styles.loadingText}>기사를 불러올 수 없습니다.</Text>
        </View>
      ) : (
      /* Main Content ScrollView */
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Article Image Placeholder with Category Badge */}
        <View style={styles.imageContainer}>
          <View style={styles.imagePlaceholder}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                {article.strategies[0] ?? article.source_name ?? '뉴스'}
              </Text>
            </View>
          </View>
        </View>

        {/* Title and Meta Info */}
        <View style={styles.metaContainer}>
          <Text style={styles.articleTitle}>
            {article.display_title ?? article.title_original}
          </Text>
          <Text style={styles.articleMeta}>
            {article.source_name ?? '뉴스'} • {formatPublishedAt(article.published_at)}
          </Text>
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Article Body */}
        <Text style={styles.articleBody}>
          {article.content_translated ?? article.content ?? article.display_summary ?? ''}
        </Text>

        {/* AI Summary Badge and Section */}
        {article.display_summary ? (
          <View style={styles.aiSummarySection}>
            <View style={styles.aiSummaryHeader}>
              <View style={styles.aiBadge}>
                <Text style={styles.aiBadgeText}>AI 요약</Text>
              </View>
            </View>
            <Text style={styles.aiSummaryText}>{article.display_summary}</Text>
          </View>
        ) : null}

        {/* Original Article Button */}
        <Pressable
          onPress={handleOriginalPress}
          style={({ pressed }) => [styles.originalBtn, pressed && styles.pressed]}
        >
          <IconLabel
            color={colors.primary}
            icon="open-in-new"
            iconColor={colors.primary}
            iconSize={16}
            label="원본 기사 보기"
            textStyle={styles.originalBtnText}
          />
        </Pressable>

        {/* 관련 기사 (시맨틱 검색 결과) */}
        {related.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>관련 기사</Text>
            <View style={styles.relatedList}>
              {related.map((item) => (
                <Pressable
                  key={item.article_id}
                  onPress={() => navigation.push('NewsDetail', { newsId: item.article_id })}
                  style={({ pressed }) => [styles.relatedCard, pressed && styles.pressed]}
                >
                  <View style={styles.relatedCardBody}>
                    {item.source_name ? (
                      <View style={styles.newsBadge}>
                        <Text style={styles.newsBadgeText}>{item.source_name}</Text>
                      </View>
                    ) : null}
                    <Text numberOfLines={2} style={styles.newsTitle}>
                      {item.title}
                    </Text>
                    {item.summary ? (
                      <Text numberOfLines={2} style={styles.relatedSummary}>
                        {item.summary}
                      </Text>
                    ) : null}
                    <Text style={styles.newsTime}>{formatPublishedAt(item.published_at)}</Text>
                  </View>
                  <Text style={styles.relatedChevron}>›</Text>
                </Pressable>
              ))}
            </View>
          </>
        ) : null}
      </ScrollView>
      )}

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
    flex: 1,
    backgroundColor: colors.background,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  loadingText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
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
  headerRight: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  scrapBtn: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1.5,
    height: 40,
    justifyContent: 'center',
    paddingHorizontal: 14,
  },
  scrapBtnSaved: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  scrapBtnDisabled: {
    opacity: 0.45,
  },
  scrapBtnText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  scrapBtnTextSaved: {
    color: colors.primary,
    fontWeight: '800',
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 24,
  },
  imageContainer: {
    width: '100%',
    height: 200,
    borderRadius: 24,
    overflow: 'hidden',
    marginBottom: 20,
    backgroundColor: '#EDF0ED',
    borderWidth: 1,
    borderColor: colors.border,
  },
  imagePlaceholder: {
    flex: 1,
    padding: 16,
    justifyContent: 'flex-end',
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: '#3E654F',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  badgeText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '700',
  },
  metaContainer: {
    marginBottom: 16,
    gap: 8,
  },
  articleTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.text,
    lineHeight: 28,
  },
  articleMeta: {
    fontSize: 13,
    color: colors.muted,
    fontWeight: '500',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginBottom: 20,
  },
  articleBody: {
    fontSize: 15,
    color: colors.text,
    lineHeight: 24,
    fontWeight: '400',
    marginBottom: 24,
  },
  aiSummarySection: {
    backgroundColor: '#F0F7F4',
    borderColor: '#D8ECE2',
    borderWidth: 1,
    borderRadius: 16,
    padding: 18,
    marginBottom: 24,
    gap: 10,
  },
  aiSummaryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  aiBadge: {
    backgroundColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  aiBadgeText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '800',
  },
  aiSummaryText: {
    fontSize: 14,
    color: colors.text,
    lineHeight: 20,
    fontWeight: '500',
  },
  originalBtn: {
    backgroundColor: colors.surface,
    borderColor: colors.primary,
    borderWidth: 1,
    borderRadius: 99,
    height: 48,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 32,
  },
  originalBtnText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '700',
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 12,
  },
  relatedList: {
    gap: 10,
  },
  relatedCard: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 8,
    padding: 14,
  },
  relatedCardBody: {
    flex: 1,
    gap: 5,
  },
  relatedSummary: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
  },
  relatedChevron: {
    color: colors.muted,
    fontSize: 22,
    fontWeight: '300',
  },
  newsBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primarySoft,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  newsBadgeText: {
    color: colors.primary,
    fontSize: 10,
    fontWeight: '700',
  },
  newsTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 19,
  },
  newsTime: {
    color: colors.muted,
    fontSize: 11,
  },
  bottomTab: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
    height: 72,
    justifyContent: 'space-around',
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingBottom: Platform.OS === 'ios' ? 12 : 0,
  },
  bottomTabItem: {
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    height: '100%',
  },
  bottomTabActiveBg: {
    backgroundColor: 'rgba(45, 106, 79, 0.08)',
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  bottomTabIcon: {
    fontSize: 18,
    marginBottom: 2,
  },
  bottomTabText: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '600',
  },
  bottomTabActiveText: {
    color: colors.primary,
    fontWeight: '800',
  },
  pressed: {
    opacity: 0.9,
  },
});
