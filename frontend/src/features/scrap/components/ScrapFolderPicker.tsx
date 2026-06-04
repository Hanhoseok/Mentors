import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { colors } from '@/constants/colors';
import {
  addScrap,
  createScrapFolder,
  listScrapFolders,
} from '@/features/explore/content/api';
import type {
  ScrapCreateRequest,
  ScrapFolderResponse,
} from '@/features/explore/content/types';

/** 스크랩할 기사 스냅샷 (folder_id 제외 — 모달이 채움). */
export type ScrapDraft = Omit<ScrapCreateRequest, 'folder_id'>;

/** 폴더 카드에 순환 적용할 파스텔 색상 프리셋. */
export const FOLDER_COLORS = [
  '#E1F5EE',
  '#E8F0FE',
  '#FFF1E6',
  '#F3E8FF',
  '#E6F7F1',
  '#FDE8EC',
  '#EAF2E1',
  '#FFF8E6',
] as const;

export function folderColorAt(index: number): string {
  return FOLDER_COLORS[index % FOLDER_COLORS.length];
}

interface Props {
  visible: boolean;
  draft: ScrapDraft | null;
  onClose: () => void;
  onScrapped?: (folderName: string) => void;
}

export function ScrapFolderPicker({ visible, draft, onClose, onScrapped }: Props) {
  const [folders, setFolders] = useState<ScrapFolderResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');

  useEffect(() => {
    if (!visible) return;
    let active = true;
    setIsLoading(true);
    setCreating(false);
    setNewName('');
    listScrapFolders()
      .then((data) => { if (active) setFolders(data); })
      .catch(() => { if (active) setFolders([]); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [visible]);

  async function handlePickFolder(folder: ScrapFolderResponse) {
    if (!draft || saving) return;
    setSaving(true);
    try {
      await addScrap({ ...draft, folder_id: folder.id });
      onScrapped?.(folder.name);
      onClose();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        Alert.alert('스크랩', `이미 '${folder.name}' 폴더에 저장된 기사예요.`);
      } else {
        Alert.alert('스크랩', '저장에 실패했어요. 잠시 후 다시 시도해 주세요.');
      }
    } finally {
      setSaving(false);
    }
  }

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
      // 새 폴더를 만들면 바로 그 폴더에 저장
      if (draft) {
        await addScrap({ ...draft, folder_id: folder.id });
        onScrapped?.(folder.name);
        onClose();
      }
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

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.handle} />
          <Text style={styles.title}>스크랩 폴더에 저장</Text>
          <Text style={styles.subtitle}>기존 폴더를 고르거나 새 폴더를 만들어 보세요.</Text>

          {isLoading ? (
            <View style={styles.loadingBox}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : (
            <ScrollView
              style={styles.list}
              contentContainerStyle={styles.listContent}
              showsVerticalScrollIndicator={false}
            >
              {folders.length === 0 ? (
                <Text style={styles.emptyText}>
                  아직 폴더가 없어요. 새 폴더를 만들어 저장하세요.
                </Text>
              ) : (
                folders.map((folder, idx) => (
                  <Pressable
                    key={folder.id}
                    onPress={() => handlePickFolder(folder)}
                    disabled={saving}
                    style={({ pressed }) => [styles.folderRow, pressed && styles.pressed]}
                  >
                    <View
                      style={[
                        styles.folderSwatch,
                        { backgroundColor: folder.color ?? folderColorAt(idx) },
                      ]}
                    >
                      <Text style={styles.folderSwatchIcon}>🗂️</Text>
                    </View>
                    <View style={styles.folderInfo}>
                      <Text style={styles.folderName}>{folder.name}</Text>
                      <Text style={styles.folderCount}>{folder.scrap_count}개</Text>
                    </View>
                    <Text style={styles.folderChevron}>＋</Text>
                  </Pressable>
                ))
              )}

              {creating ? (
                <View style={styles.createRow}>
                  <TextInput
                    style={styles.createInput}
                    value={newName}
                    onChangeText={setNewName}
                    placeholder="새 폴더 이름"
                    placeholderTextColor="#A4A9A5"
                    autoFocus
                    returnKeyType="done"
                    onSubmitEditing={handleCreateFolder}
                    maxLength={20}
                  />
                  <Pressable
                    onPress={handleCreateFolder}
                    disabled={saving || !newName.trim()}
                    style={({ pressed }) => [
                      styles.createBtn,
                      (saving || !newName.trim()) && styles.createBtnDisabled,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.createBtnText}>만들기</Text>
                  </Pressable>
                </View>
              ) : (
                <Pressable
                  onPress={() => setCreating(true)}
                  style={({ pressed }) => [styles.newFolderBtn, pressed && styles.pressed]}
                >
                  <Text style={styles.newFolderText}>＋ 새 폴더 만들기</Text>
                </Pressable>
              )}
            </ScrollView>
          )}

          <Pressable onPress={onClose} style={styles.cancelBtn}>
            <Text style={styles.cancelText}>닫기</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    backgroundColor: 'rgba(0,0,0,0.4)',
    flex: 1,
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '80%',
    paddingBottom: 28,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  handle: {
    alignSelf: 'center',
    backgroundColor: colors.border,
    borderRadius: 3,
    height: 5,
    marginBottom: 14,
    width: 44,
  },
  title: {
    color: colors.text,
    fontSize: 19,
    fontWeight: '800',
  },
  subtitle: {
    color: colors.muted,
    fontSize: 13,
    marginBottom: 14,
    marginTop: 4,
  },
  loadingBox: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  list: {
    flexGrow: 0,
  },
  listContent: {
    gap: 10,
    paddingBottom: 6,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 14,
    paddingVertical: 16,
    textAlign: 'center',
  },
  folderRow: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 14,
    padding: 12,
  },
  folderSwatch: {
    alignItems: 'center',
    borderRadius: 12,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  folderSwatchIcon: {
    fontSize: 20,
  },
  folderInfo: {
    flex: 1,
    gap: 2,
  },
  folderName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  folderCount: {
    color: colors.muted,
    fontSize: 12,
  },
  folderChevron: {
    color: colors.primary,
    fontSize: 24,
    fontWeight: '700',
    paddingHorizontal: 6,
  },
  newFolderBtn: {
    alignItems: 'center',
    borderColor: colors.primary,
    borderRadius: 16,
    borderStyle: 'dashed',
    borderWidth: 1.5,
    paddingVertical: 14,
  },
  newFolderText: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '700',
  },
  createRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  createInput: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    color: colors.text,
    flex: 1,
    fontSize: 14,
    height: 48,
    paddingHorizontal: 14,
  },
  createBtn: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 14,
    height: 48,
    justifyContent: 'center',
    paddingHorizontal: 18,
  },
  createBtnDisabled: {
    opacity: 0.5,
  },
  createBtnText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  cancelBtn: {
    alignItems: 'center',
    marginTop: 14,
    paddingVertical: 12,
  },
  cancelText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.85,
  },
});
