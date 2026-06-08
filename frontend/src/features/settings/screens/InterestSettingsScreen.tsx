import { useEffect, useMemo, useState } from 'react';
import { useNavigation } from '@react-navigation/native';
import { type NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import axios from 'axios';
import { colors } from '@/constants/colors';
import { AppIcon } from '@/components/AppIcon';
import {
  addMyKeyword,
  listIndustries,
  listMyKeywords,
  removeMyKeyword,
} from '@/features/explore/content/api';
import type { IndustryItem } from '@/features/explore/content/types';
import { getOnboardingStatus, saveOnboardingProfile } from '@/features/onboarding/api';
import type { InterestTag } from '@/features/onboarding/types';
import { buildLearningPreferencesPayload } from '@/features/settings/logic';
import { useUserStore } from '@/store/userStore';
import type { AppStackParamList } from '@/navigation/types';
import { getIndustryIconName, type AppIconName } from '@/ui/iconTokens';

type Nav = NativeStackNavigationProp<AppStackParamList, 'InterestSettings'>;

// 산업 하위 키워드(label_ko) → 온보딩 InterestTag 매핑.
// 매핑 없는 라벨은 user_keyword에만 저장되고 onboarding profile.interests에는 반영 안 됨.
const SUB_KEYWORD_TO_INTEREST: Record<string, InterestTag> = {
  // IT기술
  인공지능: 'ai',
  클라우드: 'it',
  소프트웨어: 'it',
  보안: 'it',
  인터넷: 'it',
  양자컴퓨터: 'tech',
  'IT솔루션 구축': 'it',
  // 반도체
  '반도체 부품소재': 'semiconductor',
  '반도체 장비': 'semiconductor',
  '반도체 파운드리': 'semiconductor',
  '반도체 패키징': 'semiconductor',
  '반도체 팹리스': 'semiconductor',
  종합반도체: 'semiconductor',
  // 배터리
  배터리부품: 'battery',
  배터리소재: 'battery',
  배터리장비: 'battery',
  배터리제조: 'battery',
  '폐배터리 재활용': 'battery',
  // 바이오 + 의료
  바이오서비스: 'bio',
  바이오시밀러: 'bio',
  바이오신약: 'bio',
  의료기기: 'bio',
  의료서비스: 'bio',
  제약: 'bio',
  // 금융
  결제서비스: 'finance',
  금융그룹: 'finance',
  금융기기: 'finance',
  금융상품거래소: 'finance',
  벤처캐피탈: 'finance',
  보험: 'finance',
  신용평가: 'finance',
  암호화폐: 'crypto',
  은행: 'finance',
  증권: 'finance',
  카드: 'finance',
  // 방위산업물자 + 드론
  방위산업: 'defense',
  드론: 'defense',
  // 전력에너지 + 원유
  '신재생 에너지': 'energy',
  '원자력 발전': 'energy',
  전기설비: 'energy',
  화력발전: 'energy',
  원유개발: 'energy',
  원유정제: 'energy',
  // 엔터테인먼트
  광고: 'entertainment-media',
  '동영상 플랫폼': 'entertainment-media',
  방송: 'entertainment-media',
  영화: 'entertainment-media',
  웹툰: 'entertainment-media',
  음원: 'entertainment-media',
  출판: 'entertainment-media',
  캐릭터: 'entertainment-media',
  // 화장품 / 의류 / 유통 / 음식료 / 여행 / 생활용품
  '화장품 브랜드': 'fashion-consumer',
  '화장품 제조': 'fashion-consumer',
  섬유: 'fashion-consumer',
  '의류 브랜드': 'fashion-consumer',
  의류제조: 'fashion-consumer',
  대형마트: 'fashion-consumer',
  면세점: 'fashion-consumer',
  백화점: 'fashion-consumer',
  온라인쇼핑: 'fashion-consumer',
  편의점: 'fashion-consumer',
  음식료: 'fashion-consumer',
  렌터카: 'fashion-consumer',
  여행플랫폼: 'fashion-consumer',
  카지노: 'fashion-consumer',
  '호텔과 리조트': 'fashion-consumer',
  그릇: 'fashion-consumer',
  마스크: 'fashion-consumer',
  // 자동차 / 스마트폰 / 통신 / 디스플레이 → tech
  수소차: 'tech',
  전기차: 'tech',
  '전기차 부품': 'tech',
  '스마트폰 부품': 'tech',
  '스마트폰 제조': 'tech',
  이동통신사: 'tech',
  통신장비: 'tech',
  '디스플레이 부품소재': 'tech',
  '디스플레이 장비': 'tech',
  '디스플레이 패널': 'tech',
  LED: 'tech',
  // 리츠 → etf (부동산 펀드 묶음)
  '상업용 리츠': 'etf',
  '오피스 리츠': 'etf',
  '인프라 리츠': 'etf',
  '주거용 리츠': 'etf',
  // 금속 → value (원자재)
  광산개발: 'value',
  구리: 'value',
  아연: 'value',
  알루미늄: 'value',
  철강: 'value',
  // 화학 → value (원자재/산업재)
  '비료와 농약': 'value',
  '산업용 가스': 'value',
  화학원료: 'value',
  화학제품: 'value',
  // 탄소저감 → energy
  탄소배출권: 'energy',
  // 종이 → value
  골판지: 'value',
  백판지: 'value',
  // 조선 → value (산업재/제조)
  조선기자재: 'value',
  조선사: 'value',
  // 전자부품 → tech
  가전부품: 'tech',
  // 자동차 (잔여) → tech
  오토바이: 'tech',
  자동차부품: 'tech',
  자동차브랜드: 'tech',
  자동차유통: 'tech',
  // 유통 (잔여) → global (수출입 성격)
  무역: 'global',
  // 운송 → global / value
  물류: 'global',
  해상운송: 'global',
  항공사: 'global',
  철도: 'value',
  // 수자원 → energy (유틸리티)
  수자원: 'energy',
  // 기계 → value / tech
  '농업용 기계': 'value',
  로봇: 'tech',
  '산업용 기계': 'value',
  // 농업 → value (원자재)
  농업: 'value',
  // 교육 → entertainment-media (콘텐츠/출판) / tech (장비)
  교육서비스: 'entertainment-media',
  교육장비: 'tech',
  교육출판: 'entertainment-media',
};

const MAPPED_INTEREST_POOL: Set<InterestTag> = new Set(
  Object.values(SUB_KEYWORD_TO_INTEREST),
);

// 산업 카테고리 → 대표 아이콘 (한글명 매칭)
function iconFor(name: string): AppIconName {
  return getIndustryIconName(name);
}

// ── Industry Card ─────────────────────────────────────
interface IndustryCardProps {
  industry: IndustryItem;
  selected: Set<string>;
  onToggle: (label: string) => void;
  onToggleAll: (labels: string[], selectAll: boolean) => void;
}

function IndustryCard({ industry, selected, onToggle, onToggleAll }: IndustryCardProps) {
  const allLabels = industry.keywords.map((kw) => kw.label_ko);
  const selectedCount = allLabels.filter((l) => selected.has(l)).length;
  const allSelected = allLabels.length > 0 && selectedCount === allLabels.length;

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={styles.iconBox}>
          <AppIcon color={colors.primary} name={iconFor(industry.name_ko)} size={22} />
        </View>
        {/* 분야명 자체가 버튼 — 누르면 그 분야 전체를 관심사로 토글 */}
        <Pressable
          onPress={() => onToggleAll(allLabels, !allSelected)}
          disabled={allLabels.length === 0}
          style={({ pressed }) => [
            styles.cardTitleBtn,
            allSelected && styles.cardTitleBtnActive,
            pressed && styles.pressed,
          ]}
        >
          <Text style={[styles.cardTitle, allSelected && styles.cardTitleActive]}>
            {industry.name_ko}
          </Text>
        </Pressable>
      </View>
      <View style={styles.pillGrid}>
        {industry.keywords.map((kw) => {
          const isSelected = selected.has(kw.label_ko);
          return (
            <Pressable
              key={kw.id}
              onPress={() => onToggle(kw.label_ko)}
              style={[styles.pill, isSelected && styles.pillSelected]}
            >
              <Text style={[styles.pillText, isSelected && styles.pillTextSelected]}>
                {kw.label_ko}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

// ── Main Screen ────────────────────────────────────────
export function InterestSettingsScreen() {
  const accessToken = useUserStore((s) => s.accessToken);
  const navigation = useNavigation<Nav>();
  const queryClient = useQueryClient();

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const industriesQuery = useQuery({
    queryKey: ['content-industries'],
    queryFn: listIndustries,
    enabled: Boolean(accessToken),
    staleTime: 1000 * 60 * 30,
  });

  const userKeywordsQuery = useQuery({
    queryKey: ['user-keywords', accessToken],
    queryFn: listMyKeywords,
    enabled: Boolean(accessToken),
  });

  const onboardingQuery = useQuery({
    queryKey: ['onboarding-status', accessToken],
    queryFn: getOnboardingStatus,
    enabled: Boolean(accessToken),
    retry: 0,
  });

  // 전체 산업 sub label 집합 (manual 키워드와 분리하기 위한 풀)
  const industryLabelPool = useMemo(() => {
    const set = new Set<string>();
    industriesQuery.data?.forEach((ind) =>
      ind.keywords.forEach((k) => set.add(k.label_ko)),
    );
    return set;
  }, [industriesQuery.data]);

  // 현재 user_keyword 중 산업 풀에 속한 것만 초기 선택으로 hydration
  const initialSelected = useMemo(() => {
    const set = new Set<string>();
    userKeywordsQuery.data?.items.forEach((uk) => {
      if (industryLabelPool.has(uk.keyword)) set.add(uk.keyword);
    });
    return set;
  }, [userKeywordsQuery.data, industryLabelPool]);

  // 삭제 mutation에 필요한 keyword string → user_keyword id 매핑
  const userKeywordIdByLabel = useMemo(() => {
    const map = new Map<string, number>();
    userKeywordsQuery.data?.items.forEach((uk) => {
      map.set(uk.keyword, uk.id);
    });
    return map;
  }, [userKeywordsQuery.data]);

  useEffect(() => {
    if (hydrated) return;
    if (industriesQuery.data && userKeywordsQuery.data) {
      setSelected(new Set(initialSelected));
      setHydrated(true);
    }
  }, [hydrated, industriesQuery.data, userKeywordsQuery.data, initialSelected]);

  // 선택된 sub-keyword들에서 InterestTag 집합을 도출.
  function deriveInterestTags(labels: Set<string>): Set<InterestTag> {
    const tags = new Set<InterestTag>();
    labels.forEach((label) => {
      const tag = SUB_KEYWORD_TO_INTEREST[label];
      if (tag) tags.add(tag);
    });
    return tags;
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      // 1) user_keyword diff sync
      const toAdd: string[] = [];
      const toRemove: number[] = [];
      selected.forEach((label) => {
        if (!initialSelected.has(label)) toAdd.push(label);
      });
      initialSelected.forEach((label) => {
        if (!selected.has(label)) {
          const id = userKeywordIdByLabel.get(label);
          if (id !== undefined) toRemove.push(id);
        }
      });

      for (const label of toAdd) {
        try {
          await addMyKeyword({ keyword: label, language: 'ko' });
        } catch (err) {
          if (axios.isAxiosError(err) && err.response?.status === 409) continue;
          throw err;
        }
      }
      for (const id of toRemove) {
        try {
          await removeMyKeyword(id);
        } catch (err) {
          if (axios.isAxiosError(err) && err.response?.status === 404) continue;
          throw err;
        }
      }

      // 2) onboarding profile.interests merge & save
      const profile = onboardingQuery.data?.profile;
      let interestsUpdated = false;
      if (profile) {
        const derived = deriveInterestTags(selected);
        // 기존 interests 중 산업 매핑 풀에 속하지 않는 태그는 보존
        // (예: 'macro', 'dividend' — 이 화면 외부에서 설정된 값)
        const preserved = profile.interests.filter(
          (t) => !MAPPED_INTEREST_POOL.has(t),
        );
        const mergedInterests = Array.from(
          new Set<InterestTag>([...preserved, ...derived]),
        );

        // 기존과 동일하면 호출 생략, 비어 있으면(서버 min_length=1) 호출 생략
        const sameAsBefore =
          mergedInterests.length === profile.interests.length &&
          mergedInterests.every((t) => profile.interests.includes(t));
        if (mergedInterests.length > 0 && !sameAsBefore) {
          await saveOnboardingProfile(
            buildLearningPreferencesPayload(profile, {
              interests: mergedInterests,
              preferredStyle: profile.preferred_style,
            }),
          );
          interestsUpdated = true;
        }
      }

      return {
        added: toAdd.length,
        removed: toRemove.length,
        interestsUpdated,
      };
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ['user-keywords', accessToken] });
      if (result.interestsUpdated) {
        await queryClient.invalidateQueries({
          queryKey: ['onboarding-status', accessToken],
        });
      }
      setFeedback(`저장됨 (추가 ${result.added} · 삭제 ${result.removed})`);
      navigation.goBack();
    },
    onError: () => {
      setFeedback('저장에 실패했어요. 잠시 후 다시 시도해 주세요.');
    },
  });

  // 초기화: 산업 풀에 속한 모든 관심 키워드를 삭제하고 선택을 비운다.
  const resetMutation = useMutation({
    mutationFn: async () => {
      const ids: number[] = [];
      userKeywordsQuery.data?.items.forEach((uk) => {
        if (industryLabelPool.has(uk.keyword)) ids.push(uk.id);
      });
      for (const id of ids) {
        try {
          await removeMyKeyword(id);
        } catch (err) {
          if (axios.isAxiosError(err) && err.response?.status === 404) continue;
          throw err;
        }
      }
      return ids.length;
    },
    onSuccess: async (count) => {
      setSelected(new Set());
      await queryClient.invalidateQueries({ queryKey: ['user-keywords', accessToken] });
      setFeedback(`관심사 ${count}개를 초기화했어요.`);
    },
    onError: () => {
      setFeedback('초기화에 실패했어요. 잠시 후 다시 시도해 주세요.');
    },
  });

  function toggleLabel(label: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }

  function toggleAllLabels(labels: string[], selectAll: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (selectAll) {
        labels.forEach((l) => next.add(l));
      } else {
        labels.forEach((l) => next.delete(l));
      }
      return next;
    });
  }

  const hasChanges = useMemo(() => {
    if (selected.size !== initialSelected.size) return true;
    for (const k of selected) if (!initialSelected.has(k)) return true;
    return false;
  }, [selected, initialSelected]);

  const isLoading =
    industriesQuery.isLoading ||
    userKeywordsQuery.isLoading ||
    onboardingQuery.isLoading;
  const canSave = hydrated && hasChanges && !saveMutation.isPending;
  const hasInterestKeywords = (userKeywordsQuery.data?.items ?? []).some((uk) =>
    industryLabelPool.has(uk.keyword),
  );
  const canReset =
    hydrated && !resetMutation.isPending && (selected.size > 0 || hasInterestKeywords);

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Pressable onPress={() => navigation.goBack()} style={styles.backBtn} hitSlop={8}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text style={styles.headerTitle}>관심사 설정</Text>
        <Pressable
          onPress={() => canReset && resetMutation.mutate()}
          disabled={!canReset}
          style={({ pressed }) => [
            styles.resetBtn,
            !canReset && styles.resetBtnDisabled,
            pressed && canReset && styles.saveBtnPressed,
          ]}
        >
          <Text style={[styles.resetBtnText, !canReset && styles.resetBtnTextDisabled]}>
            {resetMutation.isPending ? '초기화 중' : '초기화'}
          </Text>
        </Pressable>
        <Pressable
          onPress={() => canSave && saveMutation.mutate()}
          disabled={!canSave}
          style={({ pressed }) => [
            styles.saveBtn,
            !canSave && styles.saveBtnDisabled,
            pressed && canSave && styles.saveBtnPressed,
          ]}
        >
          <Text style={[styles.saveBtnText, !canSave && styles.saveBtnTextDisabled]}>
            {saveMutation.isPending ? '저장 중' : '설정'}
          </Text>
        </Pressable>
      </View>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.description}>
            관심 있는 산업 분야의 세부 키워드를 선택해 주세요.{'\n'}
            선택된 키워드 기반으로 뉴스가 추천돼요.
          </Text>
          <Text style={styles.countLabel}>현재 {selected.size}개 선택됨</Text>

          {industriesQuery.data?.map((ind) => (
            <IndustryCard
              key={ind.id}
              industry={ind}
              selected={selected}
              onToggle={toggleLabel}
              onToggleAll={toggleAllLabels}
            />
          ))}

          {feedback ? <Text style={styles.feedbackText}>{feedback}</Text> : null}
          {industriesQuery.isError ? (
            <Text style={styles.errorText}>산업 정보를 불러오지 못했어요.</Text>
          ) : null}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  header: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: 'row',
    gap: 8,
    height: 56,
    paddingHorizontal: 16,
  },
  backBtn: { alignItems: 'center', height: 32, justifyContent: 'center', width: 32 },
  backArrow: { color: colors.text, fontSize: 22, fontWeight: '400' },
  headerTitle: { color: colors.text, flex: 1, fontSize: 17, fontWeight: '700' },
  saveBtn: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 10,
    justifyContent: 'center',
    minHeight: 34,
    paddingHorizontal: 14,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnPressed: { opacity: 0.85 },
  saveBtnText: { color: colors.surface, fontSize: 14, fontWeight: '700' },
  saveBtnTextDisabled: { color: colors.muted },
  resetBtn: {
    alignItems: 'center',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 10,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 34,
    paddingHorizontal: 12,
  },
  resetBtnDisabled: { opacity: 0.5 },
  resetBtnText: { color: colors.rose, fontSize: 14, fontWeight: '700' },
  resetBtnTextDisabled: { color: colors.muted },
  center: { alignItems: 'center', flex: 1, justifyContent: 'center' },
  scroll: { paddingHorizontal: 16, paddingTop: 16, paddingBottom: 40, gap: 12 },
  description: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  countLabel: { color: colors.primary, fontSize: 12, fontWeight: '600' },
  // Industry card
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 16,
    borderWidth: 1,
    gap: 12,
    padding: 14,
  },
  cardHeader: { alignItems: 'center', flexDirection: 'row', gap: 10, flexWrap: 'nowrap' },
  iconBox: {
    alignItems: 'center',
    backgroundColor: colors.primarySoft,
    borderRadius: 10,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  iconText: { fontSize: 18 },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: '700' },
  cardTitleActive: { color: colors.surface },
  cardTitleBtn: {
    alignSelf: 'flex-start',
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  cardTitleBtnActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pressed: { opacity: 0.8 },
  // Pill grid (wrap)
  pillGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: {
    backgroundColor: colors.background,
    borderColor: colors.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  pillSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  pillText: { color: colors.text, fontSize: 13, fontWeight: '600' },
  pillTextSelected: { color: colors.surface },
  // Misc
  feedbackText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
});
