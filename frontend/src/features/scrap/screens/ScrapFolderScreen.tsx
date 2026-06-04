import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  useNavigation,
  useRoute,
  useFocusEffect,
  type RouteProp,
} from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import type { AppStackParamList } from '@/navigation/types';
import { listMyScraps, removeScrap } from '@/features/explore/content/api';
import type { ScrapResponse } from '@/features/explore/content/types';
import { BulkDeleteSheet } from '@/features/scrap/components/BulkDeleteSheet';

type RouteProps = RouteProp<AppStackParamList, 'ScrapFolder'>;

const DAY = 86_400_000;

/** 스크랩 생성 시각을 기준으로 시간대 그룹 라벨을 만든다. */
function bucketOf(createdAt: string): string {
  const created = new Date(createdAt);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = created.getTime();
  if (t >= startOfToday) return '오늘';
  if (t >= startOfToday - DAY) return '어제';
  if (t >= startOfToday - 7 * DAY) return '이번 주';
  if (t >= startOfToday - 30 * DAY) return '지난 달';
  return '이전';
}

const BUCKET_ORDER = ['오늘', '어제', '이번 주', '지난 달', '이전'];

function formatTime(value: string | null): string {
  if (!value) return '';
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function ScrapFolderScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const route = useRoute<RouteProps>();
  const { folderId, folderName } = route.params;

  const [scraps, setScraps] = useState<ScrapResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const reload = useCallback(() => {
    let active = true;
    setIsLoading(true);
    listMyScraps({ folderId, limit: 200 })
      .then((data) => { if (active) setScraps(data); })
      .catch(() => { if (active) setScraps([]); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [folderId]);

  useFocusEffect(reload);

  function openScrap(item: ScrapResponse) {
    navigation.navigate('RssArticleSummary', {
      ...(item.article_id != null ? { article_id: item.article_id } : {}),
      title: item.title,
      url: item.url,
      source_name: item.source_name,
      published_at: item.published_at,
      image_url: item.image_url,
      summary: item.summary,
      content: null,
    });
  }

  async function handleDeleteScraps(ids: number[]) {
    await Promise.all(ids.map((id) => removeScrap(id)));
    const idSet = new Set(ids);
    setScraps((prev) => prev.filter((s) => !idSet.has(s.id)));
  }

  // 시간대 버킷으로 그룹화 (최신순 유지)
  const groups = BUCKET_ORDER.map((label) => ({
    label,
    items: scraps.filter((s) => bucketOf(s.created_at) === label),
  })).filter((g) => g.items.length > 0);

  return (
    <SafeAreaView style={styles.screen} edges={['top', 'bottom']}>
      {/* 헤더 */}
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text numberOfLines={1} style={styles.headerTitle}>
          {folderName}
        </Text>
        {scraps.length > 0 ? (
          <Pressable
            onPress={() => setDeleteOpen(true)}
            style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
          >
            <Text style={styles.manageBtnText}>선택 삭제</Text>
          </Pressable>
        ) : (
          <Text style={styles.headerCount}>{scraps.length}개</Text>
        )}
      </View>

      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : scraps.length === 0 ? (
        <View style={styles.centerBox}>
          <Text style={styles.emptyTitle}>이 폴더는 비어 있어요</Text>
          <Text style={styles.emptyDesc}>
            뉴스 상세에서 🔖 버튼으로 이 폴더에 기사를 담아 보세요.
          </Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          {groups.map((group) => (
            <View key={group.label} style={styles.group}>
              <Text style={styles.groupLabel}>{group.label}</Text>
              <View style={styles.cardList}>
                {group.items.map((item) => (
                  <Pressable
                    key={item.id}
                    onPress={() => openScrap(item)}
                    style={({ pressed }) => [styles.card, pressed && styles.pressed]}
                  >
                    {item.image_url ? (
                      <Image
                        source={{ uri: item.image_url }}
                        style={styles.thumb}
                        resizeMode="cover"
                      />
                    ) : (
                      <View style={[styles.thumb, styles.thumbEmpty]}>
                        <Text style={styles.thumbIcon}>📰</Text>
                      </View>
                    )}
                    <View style={styles.cardBody}>
                      {item.category || item.source_name ? (
                        <View style={styles.badge}>
                          <Text style={styles.badgeText}>
                            {item.category ?? item.source_name}
                          </Text>
                        </View>
                      ) : null}
                      <Text numberOfLines={2} style={styles.cardTitle}>
                        {item.title}
                      </Text>
                      <Text style={styles.cardTime}>{formatTime(item.created_at)}</Text>
                    </View>
                  </Pressable>
                ))}
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {/* 스크랩 다중 삭제 시트 */}
      <BulkDeleteSheet
        visible={deleteOpen}
        title={`${folderName} · 스크랩 삭제`}
        noun="스크랩"
        items={scraps}
        keyOf={(s) => s.id}
        emptyText="삭제할 스크랩이 없어요."
        onClose={() => setDeleteOpen(false)}
        onConfirm={handleDeleteScraps}
        renderRow={(item, _selected) => (
          <View style={styles.deleteRow}>
            {item.image_url ? (
              <Image
                source={{ uri: item.image_url }}
                style={styles.deleteRowThumb}
                resizeMode="cover"
              />
            ) : (
              <View style={[styles.deleteRowThumb, styles.thumbEmpty]}>
                <Text style={styles.thumbIcon}>📰</Text>
              </View>
            )}
            <View style={styles.deleteRowInfo}>
              <Text numberOfLines={2} style={styles.deleteRowTitle}>
                {item.title}
              </Text>
              <Text style={styles.deleteRowTime}>{formatTime(item.created_at)}</Text>
            </View>
          </View>
        )}
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
    gap: 10,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: {
    alignItems: 'center',
    height: 36,
    justifyContent: 'center',
    width: 32,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
  },
  headerTitle: {
    color: colors.text,
    flex: 1,
    fontSize: 19,
    fontWeight: '800',
  },
  headerCount: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
  },
  manageBtn: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 99,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  manageBtnText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  deleteRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
  },
  deleteRowThumb: {
    backgroundColor: '#EDF0ED',
    borderRadius: 10,
    height: 52,
    width: 52,
  },
  deleteRowInfo: {
    flex: 1,
    gap: 3,
  },
  deleteRowTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 19,
  },
  deleteRowTime: {
    color: colors.muted,
    fontSize: 11,
  },
  centerBox: {
    alignItems: 'center',
    flex: 1,
    gap: 8,
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '800',
  },
  emptyDesc: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  content: {
    paddingBottom: 32,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  group: {
    marginBottom: 22,
  },
  groupLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 10,
  },
  cardList: {
    gap: 10,
  },
  card: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    overflow: 'hidden',
    padding: 10,
  },
  thumb: {
    backgroundColor: '#EDF0ED',
    borderRadius: 12,
    height: 64,
    width: 64,
  },
  thumbEmpty: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  thumbIcon: {
    fontSize: 24,
  },
  cardBody: {
    flex: 1,
    gap: 4,
    paddingRight: 4,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primarySoft,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: {
    color: colors.primary,
    fontSize: 10,
    fontWeight: '700',
  },
  cardTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 19,
  },
  cardTime: {
    color: colors.muted,
    fontSize: 11,
  },
  pressed: {
    opacity: 0.85,
  },
});
