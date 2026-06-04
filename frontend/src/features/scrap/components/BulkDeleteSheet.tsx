import { useEffect, useState, type ReactNode } from 'react';
import {
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';

interface BulkDeleteSheetProps<T> {
  visible: boolean;
  title: string;
  /** 삭제 단위 명사 — 확인 문구에 사용. 예: '폴더', '스크랩' */
  noun: string;
  items: T[];
  keyOf: (item: T) => number;
  /** 각 행의 시각적 내용 (선택 체크 표시는 시트가 감싼다). */
  renderRow: (item: T, selected: boolean) => ReactNode;
  emptyText?: string;
  onClose: () => void;
  /** 선택된 id들 삭제 실행. 완료 후 시트가 닫힌다. */
  onConfirm: (ids: number[]) => Promise<void> | void;
}

/**
 * 폴더/스크랩 등을 다중 선택해 삭제하는 풀스크린 시트.
 *
 * - 개별 행 탭 → 선택 토글
 * - 전체 선택 / 선택 취소
 * - 삭제 → "삭제하시겠습니까?" 확인 후 onConfirm 실행
 * - 되돌아가기(onClose) → 그냥 닫기
 */
export function BulkDeleteSheet<T>({
  visible,
  title,
  noun,
  items,
  keyOf,
  renderRow,
  emptyText,
  onClose,
  onConfirm,
}: BulkDeleteSheetProps<T>) {
  const [selected, setSelected] = useState<number[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // 시트를 열 때마다 선택/확인창 초기화
  useEffect(() => {
    if (visible) {
      setSelected([]);
      setConfirmOpen(false);
    }
  }, [visible]);

  const allSelected = items.length > 0 && selected.length === items.length;

  function toggle(id: number) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  function toggleAll() {
    setSelected(allSelected ? [] : items.map(keyOf));
  }

  // 확인창 띄우기 (웹에서도 동작하도록 Alert 대신 커스텀 모달 사용)
  function requestDelete() {
    if (selected.length === 0) return;
    setConfirmOpen(true);
  }

  async function doDelete() {
    setDeleting(true);
    try {
      await onConfirm(selected);
      setConfirmOpen(false);
      onClose();
    } catch {
      setConfirmOpen(false);
      Alert.alert('삭제', '삭제 중 문제가 발생했어요. 다시 시도해 주세요.');
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={styles.screen} edges={['top', 'bottom']}>
        {/* 헤더 */}
        <View style={styles.header}>
          <Pressable onPress={onClose} style={styles.backBtn}>
            <Text style={styles.backArrow}>←</Text>
          </Pressable>
          <Text style={styles.headerTitle}>{title}</Text>
          <Pressable onPress={toggleAll} style={styles.selectAllBtn}>
            <Text style={styles.selectAllText}>
              {allSelected ? '선택 취소' : '전체 선택'}
            </Text>
          </Pressable>
        </View>

        <Text style={styles.countLine}>
          {selected.length > 0 ? `${selected.length}개 선택됨` : `${items.length}개`}
        </Text>

        {/* 리스트 */}
        {items.length === 0 ? (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyText}>{emptyText ?? '항목이 없습니다.'}</Text>
          </View>
        ) : (
          <ScrollView
            contentContainerStyle={styles.list}
            showsVerticalScrollIndicator={false}
          >
            {items.map((item) => {
              const id = keyOf(item);
              const isSel = selected.includes(id);
              return (
                <Pressable
                  key={id}
                  onPress={() => toggle(id)}
                  style={({ pressed }) => [
                    styles.row,
                    isSel && styles.rowSelected,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={[styles.checkbox, isSel && styles.checkboxOn]}>
                    {isSel ? <Text style={styles.checkmark}>✓</Text> : null}
                  </View>
                  <View style={styles.rowContent}>{renderRow(item, isSel)}</View>
                </Pressable>
              );
            })}
          </ScrollView>
        )}

        {/* 하단 액션 바 — 되돌아가기는 좌상단 ← 로 대체 */}
        <View style={styles.actionBar}>
          <Pressable
            onPress={() => setSelected([])}
            disabled={selected.length === 0}
            style={({ pressed }) => [
              styles.actionBtn,
              styles.ghostBtn,
              selected.length === 0 && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.ghostBtnText}>선택 취소</Text>
          </Pressable>
          <Pressable
            onPress={requestDelete}
            disabled={deleting || selected.length === 0}
            style={({ pressed }) => [
              styles.actionBtn,
              styles.deleteBtn,
              (deleting || selected.length === 0) && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.deleteBtnText}>
              삭제{selected.length > 0 ? ` (${selected.length})` : ''}
            </Text>
          </Pressable>
        </View>

        {/* 삭제 확인 — 웹/네이티브 공통 동작 커스텀 모달 */}
        <Modal
          visible={confirmOpen}
          transparent
          animationType="fade"
          onRequestClose={() => setConfirmOpen(false)}
        >
          <View style={styles.confirmBackdrop}>
            <View style={styles.confirmCard}>
              <Text style={styles.confirmTitle}>{noun} 삭제</Text>
              <Text style={styles.confirmMsg}>
                선택한 {selected.length}개의 {noun}을(를) 삭제하시겠습니까?
              </Text>
              <View style={styles.confirmActions}>
                <Pressable
                  onPress={() => setConfirmOpen(false)}
                  disabled={deleting}
                  style={({ pressed }) => [
                    styles.confirmBtn,
                    styles.confirmCancel,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.confirmCancelText}>취소</Text>
                </Pressable>
                <Pressable
                  onPress={doDelete}
                  disabled={deleting}
                  style={({ pressed }) => [
                    styles.confirmBtn,
                    styles.confirmDelete,
                    deleting && styles.disabled,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.confirmDeleteText}>
                    {deleting ? '삭제 중…' : '삭제'}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </Modal>
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
    fontSize: 18,
    fontWeight: '800',
  },
  selectAllBtn: {
    backgroundColor: colors.primarySoft,
    borderRadius: 99,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  selectAllText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
  countLine: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    paddingHorizontal: 20,
    paddingTop: 12,
  },
  list: {
    gap: 10,
    paddingBottom: 16,
    paddingHorizontal: 16,
    paddingTop: 10,
  },
  emptyBox: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
    padding: 32,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 14,
    textAlign: 'center',
  },
  row: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    padding: 12,
  },
  rowSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
  },
  checkbox: {
    alignItems: 'center',
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 2,
    height: 24,
    justifyContent: 'center',
    width: 24,
  },
  checkboxOn: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  checkmark: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '900',
    lineHeight: 16,
  },
  rowContent: {
    flex: 1,
  },
  actionBar: {
    backgroundColor: colors.surface,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 10,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 12,
  },
  actionBtn: {
    alignItems: 'center',
    borderRadius: 14,
    flex: 1,
    justifyContent: 'center',
    paddingVertical: 14,
  },
  ghostBtn: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderWidth: 1,
  },
  ghostBtnText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  deleteBtn: {
    backgroundColor: colors.rose,
  },
  deleteBtnText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '800',
  },
  disabled: {
    opacity: 0.45,
  },
  pressed: {
    opacity: 0.85,
  },
  // ── 삭제 확인 모달 ──
  confirmBackdrop: {
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.45)',
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 32,
  },
  confirmCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    gap: 8,
    maxWidth: 420,
    padding: 22,
    width: '100%',
  },
  confirmTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  confirmMsg: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 8,
  },
  confirmActions: {
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'flex-end',
  },
  confirmBtn: {
    alignItems: 'center',
    borderRadius: 12,
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingVertical: 11,
  },
  confirmCancel: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderWidth: 1,
  },
  confirmCancelText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  confirmDelete: {
    backgroundColor: colors.rose,
  },
  confirmDeleteText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '800',
  },
});

