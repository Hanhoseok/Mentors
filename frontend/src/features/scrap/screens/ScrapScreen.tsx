import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
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
import { colors } from '@/constants/colors';
import { AppIcon } from '@/components/AppIcon';
import type { AppStackParamList } from '@/navigation/types';
import {
  createScrapFolder,
  listMyScraps,
  listScrapFolders,
  removeScrapFolder,
} from '@/features/explore/content/api';
import type {
  ScrapFolderResponse,
  ScrapResponse,
} from '@/features/explore/content/types';
import { folderColorAt } from '@/features/scrap/components/ScrapFolderPicker';
import { BulkDeleteSheet } from '@/features/scrap/components/BulkDeleteSheet';
import { formatRelativeTime } from '@/utils';

export function ScrapScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();

  const [folders, setFolders] = useState<ScrapFolderResponse[]>([]);
  const [recent, setRecent] = useState<ScrapResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);

  const [folderDeleteOpen, setFolderDeleteOpen] = useState(false);

  const reload = useCallback(() => {
    let active = true;
    setIsLoading(true);
    Promise.all([listScrapFolders(), listMyScraps({ limit: 20 })])
      .then(([f, s]) => {
        if (!active) return;
        setFolders(f);
        setRecent(s);
      })
      .catch(() => {
        if (!active) return;
        setFolders([]);
        setRecent([]);
      })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  useFocusEffect(reload);

  async function handleCreateFolder() {
    const name = newName.trim();
    if (!name || saving) return;
    setSaving(true);
    try {
      const folder = await createScrapFolder({
        name,
        color: folderColorAt(folders.length),
      });
      setFolders((prev) => [...prev, folder]);
      setNewName('');
      setCreating(false);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      Alert.alert(
        '폴더 추가',
        status === 409 ? '같은 이름의 폴더가 이미 있어요.' : '폴더를 만들지 못했어요.',
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteFolders(ids: number[]) {
    // allSettled — 일부 실패해도 성공한 폴더는 UI에서 즉시 제거.
    const results = await Promise.allSettled(ids.map((id) => removeScrapFolder(id)));
    const okIds = new Set(ids.filter((_, i) => results[i].status === 'fulfilled'));
    if (okIds.size > 0) {
      setFolders((prev) => prev.filter((f) => !okIds.has(f.id)));
      setRecent((prev) =>
        prev.filter((s) => s.folder_id == null || !okIds.has(s.folder_id)),
      );
    }
    // 하나라도 실패하면 시트가 에러를 표시하도록 throw (성공분은 이미 반영됨).
    if (okIds.size !== ids.length) {
      throw new Error('일부 폴더 삭제에 실패했습니다.');
    }
  }

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

  return (
    <SafeAreaView style={styles.screen}>
      {/* 헤더 */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backArrow}>←</Text>
          </Pressable>
          <Text style={styles.headerTitle}>스크랩</Text>
        </View>
        {/* 스크랩 화면에서는 우측 상단 알림·프로필 아이콘을 노출하지 않음 */}
      </View>

      {isLoading ? (
        <View style={styles.centerBox}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          {/* ── 폴더 ── */}
          <View style={styles.sectionHeader}>
            <View style={styles.sectionTitleRow}>
              <Text style={styles.sectionTitle}>폴더</Text>
              <Text style={styles.sectionCount}>{folders.length}개</Text>
            </View>
            {folders.length > 0 ? (
              <Pressable
                onPress={() => setFolderDeleteOpen(true)}
                style={({ pressed }) => [styles.manageBtn, pressed && styles.pressed]}
              >
                <Text style={styles.manageBtnText}>폴더 삭제</Text>
              </Pressable>
            ) : null}
          </View>

          <View style={styles.folderGrid}>
            {folders.map((folder, idx) => (
              <Pressable
                key={folder.id}
                onPress={() =>
                  navigation.navigate('ScrapFolder', {
                    folderId: folder.id,
                    folderName: folder.name,
                  })
                }
                style={({ pressed }) => [styles.folderCard, pressed && styles.pressed]}
              >
                <View
                  style={[
                    styles.folderThumb,
                    { backgroundColor: folder.color ?? folderColorAt(idx) },
                  ]}
                >
                  <AppIcon color={colors.surface} name="folder" size={24} />
                </View>
                <Text numberOfLines={1} style={styles.folderName}>
                  {folder.name}
                </Text>
                <Text style={styles.folderCount}>{folder.scrap_count}개</Text>
              </Pressable>
            ))}

            {/* 새 폴더 추가 카드 */}
            <Pressable
              onPress={() => setCreating(true)}
              style={({ pressed }) => [styles.addCard, pressed && styles.pressed]}
            >
              <Text style={styles.addPlus}>＋</Text>
              <Text style={styles.addLabel}>새 폴더</Text>
            </Pressable>
          </View>

          {/* ── 최근 스크랩 ── */}
          <View style={[styles.sectionHeader, styles.recentHeader]}>
            <View style={styles.sectionTitleRow}>
              <Text style={styles.sectionTitle}>최근 스크랩</Text>
              <Text style={styles.sectionCount}>{recent.length}개</Text>
            </View>
          </View>

          {recent.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyTitle}>아직 스크랩한 기사가 없어요</Text>
              <Text style={styles.emptyDesc}>
                뉴스 상세에서 스크랩 버튼을 눌러 폴더에 저장해 보세요.
              </Text>
            </View>
          ) : (
            <View style={styles.recentList}>
              {recent.map((item) => (
                <Pressable
                  key={item.id}
                  onPress={() => openScrap(item)}
                  style={({ pressed }) => [styles.recentCard, pressed && styles.pressed]}
                >
                  {item.image_url ? (
                    <Image
                      source={{ uri: item.image_url }}
                      style={styles.recentThumb}
                      resizeMode="cover"
                    />
                  ) : (
                    <View style={[styles.recentThumb, styles.recentThumbEmpty]}>
                      <AppIcon color="#8B9890" name="newspaper-variant-outline" size={22} />
                    </View>
                  )}
                  <View style={styles.recentBody}>
                    {item.category || item.source_name ? (
                      <View style={styles.recentBadge}>
                        <Text style={styles.recentBadgeText}>
                          {item.category ?? item.source_name}
                        </Text>
                      </View>
                    ) : null}
                    <Text numberOfLines={3} style={styles.recentTitle}>
                      {item.title}
                    </Text>
                    <Text style={styles.recentTime}>
                      {formatRelativeTime(item.created_at)}
                    </Text>
                  </View>
                </Pressable>
              ))}
            </View>
          )}
        </ScrollView>
      )}

      {/* 새 폴더 생성 모달 */}
      <Modal
        visible={creating}
        transparent
        animationType="fade"
        onRequestClose={() => setCreating(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setCreating(false)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.modalTitle}>새 폴더 만들기</Text>
            <TextInput
              style={styles.modalInput}
              value={newName}
              onChangeText={setNewName}
              placeholder="폴더 이름 (예: 국내주식)"
              placeholderTextColor="#A4A9A5"
              autoFocus
              maxLength={30}
              returnKeyType="done"
              onSubmitEditing={handleCreateFolder}
            />
            <View style={styles.modalActions}>
              <Pressable
                onPress={() => { setCreating(false); setNewName(''); }}
                style={[styles.modalBtn, styles.modalBtnGhost]}
              >
                <Text style={styles.modalBtnGhostText}>취소</Text>
              </Pressable>
              <Pressable
                onPress={handleCreateFolder}
                disabled={!newName.trim() || saving}
                style={[
                  styles.modalBtn,
                  styles.modalBtnPrimary,
                  (!newName.trim() || saving) && styles.pressed,
                ]}
              >
                <Text style={styles.modalBtnPrimaryText}>만들기</Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {/* 폴더 다중 삭제 시트 */}
      <BulkDeleteSheet
        visible={folderDeleteOpen}
        title="폴더 삭제"
        noun="폴더"
        items={folders}
        keyOf={(f) => f.id}
        emptyText="삭제할 폴더가 없어요."
        onClose={() => setFolderDeleteOpen(false)}
        onConfirm={handleDeleteFolders}
        renderRow={(folder, _selected) => (
          <View style={styles.deleteRow}>
            <View
              style={[
                styles.deleteRowSwatch,
                { backgroundColor: folder.color ?? colors.primarySoft },
              ]}
            >
              <AppIcon color={colors.surface} name="folder" size={18} />
            </View>
            <View style={styles.deleteRowInfo}>
              <Text style={styles.deleteRowName}>{folder.name}</Text>
              <Text style={styles.deleteRowSub}>스크랩 {folder.scrap_count}개</Text>
            </View>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const CARD_GAP = 12;

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
    justifyContent: 'space-between',
    paddingBottom: 10,
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  headerLeft: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
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
    fontSize: 20,
    fontWeight: '800',
  },
  centerBox: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  content: {
    alignSelf: 'center',
    maxWidth: 720,
    paddingBottom: 32,
    paddingHorizontal: 16,
    paddingTop: 16,
    width: '100%',
  },
  sectionHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionTitleRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  recentHeader: {
    marginTop: 22,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  sectionCount: {
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
  // ── 폴더 그리드 (작게) ──
  folderGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: CARD_GAP,
  },
  folderCard: {
    width: 96,
  },
  folderThumb: {
    alignItems: 'center',
    borderRadius: 16,
    height: 72,
    justifyContent: 'center',
    marginBottom: 6,
  },
  folderIcon: {
    fontSize: 26,
  },
  folderName: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
  },
  folderCount: {
    color: colors.muted,
    fontSize: 11,
    marginTop: 1,
  },
  addCard: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: 16,
    borderStyle: 'dashed',
    borderWidth: 1.5,
    height: 72,
    justifyContent: 'center',
    width: 96,
  },
  addPlus: {
    color: colors.muted,
    fontSize: 24,
    fontWeight: '300',
  },
  addLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },
  // ── 최근 스크랩 (크게) ──
  emptyBox: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 8,
    paddingHorizontal: 24,
    paddingVertical: 40,
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
  recentList: {
    gap: 12,
  },
  recentCard: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 14,
    overflow: 'hidden',
    padding: 12,
  },
  recentThumb: {
    backgroundColor: '#EDF0ED',
    borderRadius: 14,
    height: 84,
    width: 84,
  },
  recentThumbEmpty: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  recentThumbIcon: {
    fontSize: 30,
  },
  recentBody: {
    flex: 1,
    gap: 5,
    paddingRight: 4,
  },
  recentBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primarySoft,
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 3,
  },
  recentBadgeText: {
    color: colors.primary,
    fontSize: 11,
    fontWeight: '700',
  },
  recentTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 21,
  },
  recentTime: {
    color: colors.muted,
    fontSize: 12,
  },
  // ── 삭제 시트 행 ──
  deleteRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
  },
  deleteRowSwatch: {
    alignItems: 'center',
    borderRadius: 12,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  deleteRowIcon: {
    fontSize: 20,
  },
  deleteRowInfo: {
    flex: 1,
    gap: 2,
  },
  deleteRowName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  deleteRowSub: {
    color: colors.muted,
    fontSize: 12,
  },
  // ── 새 폴더 모달 ──
  modalBackdrop: {
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.4)',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    gap: 14,
    maxWidth: 420,
    padding: 22,
    width: '100%',
  },
  modalTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  modalInput: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    color: colors.text,
    fontSize: 15,
    height: 50,
    paddingHorizontal: 14,
  },
  modalActions: {
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'flex-end',
  },
  modalBtn: {
    alignItems: 'center',
    borderRadius: 12,
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingVertical: 11,
  },
  modalBtnGhost: {
    backgroundColor: colors.background,
  },
  modalBtnGhostText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '700',
  },
  modalBtnPrimary: {
    backgroundColor: colors.primary,
  },
  modalBtnPrimaryText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.85,
  },
});
