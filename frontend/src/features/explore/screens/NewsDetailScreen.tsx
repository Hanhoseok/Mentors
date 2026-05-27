import { useState } from 'react';
import { StyleSheet, Text, View, Pressable, ScrollView, Alert, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { colors } from '@/constants/colors';
import type { AppStackParamList } from '@/navigation/types';

const ALL_NEWS = [
  {
    id: 101,
    title: '환율 1,320원대 하락 마감',
    category: '경제',
    time: '2분 전',
    body: '미 연준의 기준 금리 인하 가능성이 고조되면서 원/달러 환율이 강한 하향 압력을 받았습니다. 서울 외환시장에서 달러 대비 원화 환율은 전 거래일보다 12.30원 내린 1,320.50원에 마감했습니다. 외환시장 참가자들은 미국의 추가적인 통화 긴축 완화 기조와 한국은행의 금리 동결 스탠스에 주목하고 있습니다.',
    aiSummary: '금리 인하 기대감으로 환율이 1,320원대로 하락 마감했습니다.',
  },
  {
    id: 102,
    title: '외환시장 변동성 완화 대책 가동',
    category: '경제',
    time: '20분 전',
    body: '외환 당국은 최근 원/달러 환율 변동성 확대에 대응하기 위해 모니터링을 강화하고 필요시 유동성 조절에 나설 방침이라고 밝혔습니다. 인플레이션 지표와 외인 유입세를 중점 점검합니다. 관계기관은 급격한 쏠림 현상을 방지하는 방안을 조율 중입니다.',
    aiSummary: '급격한 쏠림 현상을 방지하기 위해 외환 시장 모니터링을 강화합니다.',
  },
  {
    id: 201,
    title: '한은, 기준금리 3.50% 동결 결정',
    category: '금융',
    time: '1시간 전',
    body: '한국은행 금융통화위원회는 오늘 통화정책방향 결정 회의를 열고 기준금리를 현재의 연 3.50% 수준으로 유지하기로 결정했습니다. 인플레이션 둔화 흐름과 가계부채 추이를 좀 더 지켜보겠다는 판단입니다. 향후 경기 전망의 불확실성이 큰 점도 영향을 준 것으로 분석됩니다.',
    aiSummary: '한은이 인플레이션 및 부채 안정성 우려로 기준금리를 연 3.50%로 동결했습니다.',
  },
  {
    id: 202,
    title: '시중 대출 금리 선제적 인하 흐름',
    category: '금융',
    time: '3시간 전',
    body: '미국 통화정책 전환 기대에 힘입어 국내 시중은행들의 고정금리형 주택담보대출 금리가 연 3% 중반대까지 선제적으로 하락하며 수요자들의 움직임이 바빠지고 있습니다. 일부 주요 은행은 하방 지지선을 강화하며 금융 소비자 유치를 위해 가산 금리를 조정하는 중입니다.',
    aiSummary: '시중 대출 고정금리가 연 3%대 중반으로 먼저 떨어지고 있습니다.',
  },
  {
    id: 301,
    title: '코스피, 기관 매도세에 하락 마감',
    category: '증시',
    time: '40분 전',
    body: '코스피 지수가 금융투자 및 기관 투자자의 강한 차익 실현 압력에 2,650선까지 후퇴했습니다. 반도체 대형주와 이차전지 밸류체인의 조정폭이 컸습니다. 외국인은 장 후반에 일부 순매수로 전환했으나 하락 흐름을 돌리기에는 부족했습니다.',
    aiSummary: '기관 매도로 코스피가 하락하며 2,650선으로 마쳤습니다.',
  },
  {
    id: 302,
    title: '바이오·소비재 섹터는 상대적 선방',
    category: '증시',
    time: '2시간 전',
    body: '대형 IT주의 조정 흐름 속에서도 신약 파이프라인 임상 모멘텀이 있는 대형 제약바이오 종목과 화장품 등 중국 소비 회복 관련주들은 강세를 나타내며 지수 하단을 지지했습니다. 업계 전반에 신흥 시장 진출 성과가 기대되고 있습니다.',
    aiSummary: '신약 모멘텀 바이오주 및 소비재 섹터는 방어세로 강세를 기록했습니다.',
  },
  {
    id: 401,
    title: '나스닥, 테크주 강세로 최고치 경신',
    category: '해외증시',
    time: '5시간 전',
    body: '뉴욕증시에서 기술주 중심의 나스닥 지수가 엔비디아와 마이크로소프트 등 인공지능 수혜주들의 지배적인 매수 우위에 힘입어 0.75% 추가 상승 마감했습니다. 시장은 대형 테크 기업들의 클라우드 매출 실적 성장세에 지속적인 호의를 보이고 있습니다.',
    aiSummary: 'AI 칩셋 강세와 주요 빅테크 매수 유입으로 최고치를 돌파했습니다.',
  },
  {
    id: 402,
    title: '엔비디아 공급 부족 지속 전망에 4% 급등',
    category: '해외증시',
    time: '8시간 전',
    body: '차세대 인공지능 반도체의 쇼티지(공급 부족) 현상이 내년까지 장기화할 것이라는 전망이 지지받으며 엔비디아 주가가 급등, 전체 빅테크의 지수를 부양했습니다. 시장 수요가 연일 최고치를 기록하며 생산 파트너들의 연장 가동 소식이 전해졌습니다.',
    aiSummary: '인공지능 칩 공급 부족 전망에 주가가 급등하며 테크주 상승을 촉발했습니다.',
  },
];

type NewsDetailRouteProp = RouteProp<AppStackParamList, 'NewsDetail'>;

export function NewsDetailScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const route = useRoute<NewsDetailRouteProp>();

  // Use state to keep track of current article being viewed, initialized with route params
  const [currentArticle, setCurrentArticle] = useState({
    id: route.params.newsId,
    title: route.params.title,
    category: route.params.category,
    time: route.params.time,
    body: route.params.body,
    aiSummary: route.params.aiSummary,
  });

  // Filter other news to show as related articles (excluding the active one)
  const relatedArticles = ALL_NEWS.filter((item) => item.id !== currentArticle.id);

  const handleRelatedPress = (article: (typeof ALL_NEWS)[0]) => {
    setCurrentArticle({
      id: article.id,
      title: article.title,
      category: article.category,
      time: article.time,
      body: article.body,
      aiSummary: article.aiSummary,
    });
  };

  return (
    <SafeAreaView style={styles.screen}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Pressable onPress={() => navigation.goBack()} style={styles.backBtn}>
            <Text style={styles.backBtnText}>←</Text>
          </Pressable>
          <Text style={styles.headerTitle}>뉴스 상세</Text>
        </View>

        <View style={styles.iconRow}>
          <Pressable
            onPress={() => Alert.alert('알림', '새로운 알림이 없습니다.')}
            style={styles.iconBtn}
          >
            <Text style={styles.iconText}>🔔</Text>
          </Pressable>
          <Pressable
            onPress={() => Alert.alert('스크랩', '스크랩 페이지 개발 중입니다.')}
            style={styles.iconBtn}
          >
            <Text style={styles.iconText}>📌</Text>
          </Pressable>
          <Pressable
            onPress={() => Alert.alert('프로필', '프로필 페이지 개발 중입니다.')}
            style={styles.iconBtn}
          >
            <Text style={styles.iconText}>👤</Text>
          </Pressable>
        </View>
      </View>

      {/* Main Content ScrollView */}
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Article Image Placeholder with Category Badge */}
        <View style={styles.imageContainer}>
          <View style={styles.imagePlaceholder}>
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{currentArticle.category}</Text>
            </View>
          </View>
        </View>

        {/* Title and Meta Info */}
        <View style={styles.metaContainer}>
          <Text style={styles.articleTitle}>{currentArticle.title}</Text>
          <Text style={styles.articleMeta}>
            {currentArticle.category} • {currentArticle.time} • 읽기 시간 약 2분
          </Text>
        </View>

        {/* Divider */}
        <View style={styles.divider} />

        {/* Article Body */}
        <Text style={styles.articleBody}>{currentArticle.body}</Text>

        {/* AI Summary Badge and Section */}
        <View style={styles.aiSummarySection}>
          <View style={styles.aiSummaryHeader}>
            <View style={styles.aiBadge}>
              <Text style={styles.aiBadgeText}>AI 요약</Text>
            </View>
          </View>
          <Text style={styles.aiSummaryText}>{currentArticle.aiSummary}</Text>
        </View>

        {/* Original Article Button */}
        <Pressable
          onPress={() =>
            Alert.alert('원본 기사', '외부 웹브라우저로 원본 기사 연결을 제공할 예정입니다.')
          }
          style={({ pressed }) => [styles.originalBtn, pressed && styles.pressed]}
        >
          <Text style={styles.originalBtnText}>원본 기사 보기</Text>
        </Pressable>

        {/* Related News List Section */}
        <Text style={styles.sectionTitle}>관련 기사</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.newsHorizontalList}
        >
          {relatedArticles.map((item) => (
            <Pressable
              key={item.id}
              onPress={() => handleRelatedPress(item)}
              style={({ pressed }) => [styles.newsCard, pressed && styles.pressed]}
            >
              <View style={styles.newsImgPlaceholder}>
                <View style={styles.newsBadge}>
                  <Text style={styles.newsBadgeText}>{item.category}</Text>
                </View>
              </View>
              <View style={styles.newsCardBody}>
                <Text numberOfLines={2} style={styles.newsTitle}>
                  {item.title}
                </Text>
                <Text style={styles.newsTime}>{item.time}</Text>
              </View>
            </Pressable>
          ))}
        </ScrollView>
      </ScrollView>

      {/* Floating Bottom Tab Bar */}
      <View style={styles.bottomTab}>
        <Pressable onPress={() => navigation.navigate('Search')} style={styles.bottomTabItem}>
          <View style={styles.bottomTabActiveBg}>
            <Text style={styles.bottomTabIcon}>🔍</Text>
            <Text style={[styles.bottomTabText, styles.bottomTabActiveText]}>탐색</Text>
          </View>
        </Pressable>

        <Pressable
          onPress={() => Alert.alert('채팅', '챗봇 채팅 화면은 S#03 구현 예정입니다.')}
          style={styles.bottomTabItem}
        >
          <Text style={styles.bottomTabIcon}>💬</Text>
          <Text style={styles.bottomTabText}>채팅</Text>
        </Pressable>

        <Pressable
          onPress={() => Alert.alert('투기장', '투기장 토론 화면은 S#05 구현 예정입니다.')}
          style={styles.bottomTabItem}
        >
          <Text style={styles.bottomTabIcon}>⚔️</Text>
          <Text style={styles.bottomTabText}>투기장</Text>
        </Pressable>
      </View>
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
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 12,
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
  iconRow: {
    flexDirection: 'row',
    gap: 8,
  },
  iconBtn: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 99,
    height: 40,
    justifyContent: 'center',
    width: 40,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconText: {
    fontSize: 18,
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 90, // Buffer for floating bottom tab
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
  newsHorizontalList: {
    gap: 12,
    paddingBottom: 8,
  },
  newsCard: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    width: 200,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.border,
  },
  newsImgPlaceholder: {
    backgroundColor: '#EDF0ED',
    height: 100,
    padding: 10,
    justifyContent: 'flex-end',
  },
  newsBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#3E654F',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  newsBadgeText: {
    color: colors.surface,
    fontSize: 10,
    fontWeight: '700',
  },
  newsCardBody: {
    padding: 12,
    gap: 6,
  },
  newsTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 18,
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
