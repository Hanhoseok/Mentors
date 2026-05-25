import { Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
import type { GrowthProgressResponse } from '@/features/growth/types';
import { getGrowthStageCopy, getUnlockLabel } from '../growth/logic';

interface GrowthProgressCardProps {
  progress: GrowthProgressResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
  requiresAuth: boolean;
  onPressPromotionTest: () => void;
}

function FeatureChips({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: string[];
  emptyLabel: string;
}) {
  return (
    <View style={styles.featureBlock}>
      <Text style={styles.featureTitle}>{title}</Text>
      {items.length > 0 ? (
        <View style={styles.featureRow}>
          {items.map((item) => (
            <View key={item} style={styles.featureChip}>
              <Text style={styles.featureChipText}>{getUnlockLabel(item)}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.featureEmpty}>{emptyLabel}</Text>
      )}
    </View>
  );
}

export function GrowthProgressCard({
  progress,
  isLoading,
  errorMessage,
  requiresAuth,
  onPressPromotionTest,
}: GrowthProgressCardProps) {
  if (requiresAuth) {
    return (
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Growth</Text>
        <Text style={styles.title}>성장 현황은 로그인 후 확인할 수 있어요</Text>
        <Text style={styles.description}>
          온보딩은 로컬에서도 이어지지만, 티어와 승급시험은 서버 계정과 연결된 뒤에 조회할 수
          있어요.
        </Text>
      </View>
    );
  }

  if (isLoading) {
    return (
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Growth</Text>
        <Text style={styles.title}>성장 현황을 불러오는 중이에요</Text>
        <Text style={styles.description}>
          현재 티어와 승급시험 정보를 서버에서 확인하고 있어요.
        </Text>
      </View>
    );
  }

  if (errorMessage) {
    return (
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Growth</Text>
        <Text style={styles.title}>성장 정보를 가져오지 못했어요</Text>
        <Text style={styles.description}>{errorMessage}</Text>
      </View>
    );
  }

  if (!progress) {
    return (
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Growth</Text>
        <Text style={styles.title}>아직 성장 데이터가 없어요</Text>
        <Text style={styles.description}>
          온보딩을 마친 뒤 다시 들어오면 티어와 이해도 게이지가 보이게 됩니다.
        </Text>
      </View>
    );
  }

  const stage = getGrowthStageCopy(progress);
  const progressWidth = `${Math.max(0, Math.min(progress.progress_percent, 100))}%` as const;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={styles.headerText}>
          <Text style={styles.eyebrow}>Growth</Text>
          <Text style={styles.title}>{stage.title}</Text>
          <Text style={styles.description}>{stage.description}</Text>
        </View>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{stage.badge}</Text>
        </View>
      </View>

      <View style={styles.tierRow}>
        <View style={styles.tierPill}>
          <Text style={styles.tierLabel}>현재 티어</Text>
          <Text style={styles.tierValue}>{progress.current_tier}</Text>
        </View>
        <View style={styles.tierPill}>
          <Text style={styles.tierLabel}>다음 티어</Text>
          <Text style={styles.tierValue}>{progress.next_tier ?? 'MAX'}</Text>
        </View>
      </View>

      <View style={styles.meterBlock}>
        <View style={styles.meterHeader}>
          <Text style={styles.meterTitle}>이해도 게이지</Text>
          <Text style={styles.meterValue}>{progress.progress_percent}%</Text>
        </View>
        <View style={styles.meterTrack}>
          <View style={[styles.meterFill, { width: progressWidth }]} />
        </View>
        <Text style={styles.meterCaption}>
          {progress.mastered_concepts}/{progress.total_concepts}개 개념 완료
        </Text>
      </View>

      <FeatureChips
        title="지금 열린 기능"
        items={progress.unlocked_features}
        emptyLabel="아직 추가로 해금된 기능이 없어요."
      />
      <FeatureChips
        title="다음 티어에서 열리는 기능"
        items={progress.next_unlocks}
        emptyLabel="다음 티어에서 새로 열릴 기능이 없어요."
      />

      {progress.promotion_test ? (
        <View style={styles.promotionBox}>
          <View style={styles.promotionHeader}>
            <View style={styles.promotionText}>
              <Text style={styles.promotionTitle}>
                {progress.promotion_test.target_tier} 승급시험 준비 완료
              </Text>
              <Text style={styles.promotionDescription}>
                객관식 {progress.promotion_test.question_count}문항, 합격 기준{' '}
                {progress.promotion_test.passing_score}점
              </Text>
            </View>
            <Pressable onPress={onPressPromotionTest} style={styles.promotionButton}>
              <Text style={styles.promotionButtonText}>시험 시작</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 20,
    gap: 18,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  headerText: {
    flex: 1,
    gap: 8,
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    lineHeight: 30,
  },
  description: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  badge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentSoft,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  badgeText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  tierRow: {
    flexDirection: 'row',
    gap: 10,
  },
  tierPill: {
    flex: 1,
    backgroundColor: colors.background,
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 4,
  },
  tierLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  tierValue: {
    color: colors.text,
    fontSize: 20,
    fontWeight: '800',
  },
  meterBlock: {
    gap: 10,
  },
  meterHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  meterTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  meterValue: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '800',
  },
  meterTrack: {
    height: 12,
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    overflow: 'hidden',
  },
  meterFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 999,
  },
  meterCaption: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  featureBlock: {
    gap: 10,
  },
  featureTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  featureRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  featureChip: {
    backgroundColor: colors.primarySoft,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  featureChipText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },
  featureEmpty: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  promotionBox: {
    backgroundColor: colors.background,
    borderRadius: 20,
    padding: 16,
  },
  promotionHeader: {
    gap: 14,
  },
  promotionText: {
    gap: 6,
  },
  promotionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: '800',
  },
  promotionDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
  promotionButton: {
    alignItems: 'center',
    backgroundColor: colors.text,
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  promotionButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
});
