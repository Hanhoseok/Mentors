import { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  Pressable,
  ScrollView,
  Alert,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';
import { colors } from '@/constants/colors';
import type { AppStackParamList } from '@/navigation/types';

interface IndicatorData {
  value: string;
  change: string;
  isUp: boolean;
  aiSummary: string;
  points: { x: number; y: number }[];
  news: {
    id: number;
    title: string;
    category: string;
    time: string;
    body: string;
    aiSummary: string;
  }[];
}

const indicatorMap: Record<string, IndicatorData> = {
  환율: {
    value: '1,320.50원',
    change: '+12.30 (+0.94%)',
    isUp: true,
    aiSummary:
      '달러/원 환율이 2주 만에 최저치를 기록했어요. 미 연준의 금리 인하 기대감이 반영된 것으로 분석됩니다.',
    points: [
      { x: 10, y: 100 },
      { x: 70, y: 95 },
      { x: 130, y: 110 },
      { x: 190, y: 80 },
      { x: 250, y: 70 },
      { x: 310, y: 50 },
      { x: 360, y: 40 },
    ],
    news: [
      {
        id: 101,
        title: '환율 1,320원대 하락 마감',
        category: '경제',
        time: '2분 전',
        body: '미 연준의 기준 금리 인하 가능성이 고조되면서 원/달러 환율이 강한 하향 압력을 받았습니다. 서울 외환시장에서 달러 대비 원화 환율은 전 거래일보다 12.30원 내린 1,320.50원에 마감했습니다.',
        aiSummary: '금리 인하 기대감으로 환율이 1,320원대로 하락 마감했습니다.',
      },
      {
        id: 102,
        title: '외환시장 변동성 완화 대책 가동',
        category: '경제',
        time: '20분 전',
        body: '외환 당국은 최근 원/달러 환율 변동성 확대에 대응하기 위해 모니터링을 강화하고 필요시 유동성 조절에 나설 방침이라고 밝혔습니다. 인플레이션 지표와 외인 유입세를 중점 점검합니다.',
        aiSummary: '급격한 쏠림 현상을 방지하기 위해 외환 시장 모니터링을 강화합니다.',
      },
    ],
  },
  금리: {
    value: '3.50%',
    change: '-0.25 (-6.67%)',
    isUp: false,
    aiSummary:
      '미국 국채 금리 급락 영향으로 한국 기준금리도 연말 인하 기대감이 시장에 선반영되고 있습니다.',
    points: [
      { x: 10, y: 30 },
      { x: 70, y: 30 },
      { x: 130, y: 55 },
      { x: 190, y: 55 },
      { x: 250, y: 80 },
      { x: 310, y: 80 },
      { x: 360, y: 95 },
    ],
    news: [
      {
        id: 201,
        title: '한은, 기준금리 3.50% 동결 결정',
        category: '금융',
        time: '1시간 전',
        body: '한국은행 금융통화위원회는 오늘 통화정책방향 결정 회의를 열고 기준금리를 현재의 연 3.50% 수준으로 유지하기로 결정했습니다. 인플레이션 둔화 흐름과 가계부채 추이를 좀 더 지켜보겠다는 판단입니다.',
        aiSummary: '한은이 인플레이션 및 부채 안정성 우려로 기준금리를 연 3.50%로 동결했습니다.',
      },
      {
        id: 202,
        title: '시중 대출 금리 선제적 인하 흐름',
        category: '금융',
        time: '3시간 전',
        body: '미국 통화정책 전환 기대에 힘입어 국내 시중은행들의 고정금리형 주택담보대출 금리가 연 3% 중반대까지 선제적으로 하락하며 수요자들의 움직임이 바빠지고 있습니다.',
        aiSummary: '시중 대출 고정금리가 연 3%대 중반으로 먼저 떨어지고 있습니다.',
      },
    ],
  },
  코스피: {
    value: '2,650.12',
    change: '-15.40 (-0.58%)',
    isUp: false,
    aiSummary:
      '외국인과 기관의 동반 차익 실현 매물이 나오면서 지수가 2,650선으로 미끄러져 마감했습니다.',
    points: [
      { x: 10, y: 40 },
      { x: 70, y: 50 },
      { x: 130, y: 45 },
      { x: 190, y: 70 },
      { x: 250, y: 65 },
      { x: 310, y: 85 },
      { x: 360, y: 90 },
    ],
    news: [
      {
        id: 301,
        title: '코스피, 기관 매도세에 하락 마감',
        category: '증시',
        time: '40분 전',
        body: '코스피 지수가 금융투자 및 기관 투자자의 강한 차익 실현 압력에 2,650선까지 후퇴했습니다. 반도체 대형주와 이차전지 밸류체인의 조정폭이 컸습니다.',
        aiSummary: '기관 매도로 코스피가 하락하며 2,650선으로 마쳤습니다.',
      },
      {
        id: 302,
        title: '바이오·소비재 섹터는 상대적 선방',
        category: '증시',
        time: '2시간 전',
        body: '대형 IT주의 조정 흐름 속에서도 신약 파이프라인 임상 모멘텀이 있는 대형 제약바이오 종목과 화장품 등 중국 소비 회복 관련주들은 강세를 나타내며 지수 하단을 지지했습니다.',
        aiSummary: '신약 모멘텀 바이오주 및 소비재 섹터는 방어세로 강세를 기록했습니다.',
      },
    ],
  },
  나스닥: {
    value: '16,210.50',
    change: '+120.40 (+0.75%)',
    isUp: true,
    aiSummary:
      '빅테크 기업들의 강력한 실적 발표와 AI 인프라 투자 견고성 증가로 지수가 연일 최고치를 갱신 중입니다.',
    points: [
      { x: 10, y: 100 },
      { x: 70, y: 80 },
      { x: 130, y: 75 },
      { x: 190, y: 55 },
      { x: 250, y: 40 },
      { x: 310, y: 35 },
      { x: 360, y: 15 },
    ],
    news: [
      {
        id: 401,
        title: '나스닥, 테크주 강세로 최고치 경신',
        category: '해외증시',
        time: '5시간 전',
        body: '뉴욕증시에서 기술주 중심의 나스닥 지수가 엔비디아와 마이크로소프트 등 인공지능 수혜주들의 지배적인 매수 우위에 힘입어 0.75% 추가 상승 마감했습니다.',
        aiSummary: 'AI 칩셋 강세와 주요 빅테크 매수 유입으로 최고치를 돌파했습니다.',
      },
      {
        id: 402,
        title: '엔비디아 공급 부족 지속 전망에 4% 급등',
        category: '해외증시',
        time: '8시간 전',
        body: '차세대 인공지능 반도체의 쇼티지(공급 부족) 현상이 내년까지 장기화할 것이라는 전망이 지지받으며 엔비디아 주가가 급등, 전체 빅테크의 지수를 부양했습니다.',
        aiSummary: '인공지능 칩 공급 부족 전망에 주가가 급등하며 테크주 상승을 촉발했습니다.',
      },
    ],
  },
};

type ActiveTab = '환율' | '금리' | '코스피' | '나스닥';

export function SearchScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const [activeTab, setActiveTab] = useState<ActiveTab>('환율');
  const [searchQuery, setSearchQuery] = useState('');

  const currentData = indicatorMap[activeTab];
  const color = currentData.isUp ? colors.primary : colors.rose;

  // Filter news based on search query
  const filteredNews = currentData.news.filter(
    (item) =>
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.body.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // SVG Line Helpers
  function buildPath(points: { x: number; y: number }[]): string {
    return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  }

  function buildAreaPath(points: { x: number; y: number }[], height: number): string {
    const linePath = buildPath(points);
    return `${linePath} L ${points[points.length - 1].x} ${height} L ${points[0].x} ${height} Z`;
  }

  return (
    <SafeAreaView style={styles.screen}>
      {/* Header Search Bar */}
      <View style={styles.header}>
        <View style={styles.searchBar}>
          <TextInput
            placeholder="종목, 뉴스, 경제 용어 검색"
            placeholderTextColor="#A4A9A5"
            style={styles.searchInput}
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
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

      {/* Top Indicators Tab Bar */}
      <View style={styles.tabBar}>
        {(['환율', '금리', '코스피', '나스닥'] as ActiveTab[]).map((tab) => (
          <Pressable
            key={tab}
            onPress={() => {
              setActiveTab(tab);
              setSearchQuery(''); // Reset search when switching tab
            }}
            style={[styles.tabItem, activeTab === tab && styles.tabItemActive]}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>{tab}</Text>
          </Pressable>
        ))}
      </View>

      {/* Main Content ScrollView */}
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {/* Metric Chart Card */}
        <View style={styles.chartCard}>
          <Text style={styles.metricValue}>{currentData.value}</Text>
          <Text style={[styles.metricChange, { color }]}>{currentData.change}</Text>

          {/* SVG Line Graph */}
          <View style={styles.chartContainer}>
            <Svg width="100%" height="100%" viewBox="0 0 370 120">
              <Defs>
                <LinearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0%" stopColor={color} stopOpacity="0.2" />
                  <Stop offset="100%" stopColor={color} stopOpacity="0.0" />
                </LinearGradient>
              </Defs>
              {/* Gradient Area */}
              <Path d={buildAreaPath(currentData.points, 120)} fill="url(#areaGrad)" />
              {/* Line */}
              <Path
                d={buildPath(currentData.points)}
                fill="none"
                stroke={color}
                strokeWidth="2.5"
              />
            </Svg>
          </View>

          {/* Time scale */}
          <View style={styles.timeRow}>
            <Text style={styles.timeText}>09:00</Text>
            <Text style={styles.timeText}>11:00</Text>
            <Text style={styles.timeText}>13:00</Text>
            <Text style={styles.timeText}>15:00</Text>
          </View>
        </View>

        {/* AI Summary Card */}
        <View style={styles.aiCard}>
          <View style={styles.aiBadge}>
            <Text style={styles.aiBadgeText}>AI</Text>
          </View>
          <Text style={styles.aiText}>{currentData.aiSummary}</Text>
        </View>

        {/* Related News List Section */}
        <Text style={styles.sectionTitle}>관련 뉴스</Text>
        {filteredNews.length > 0 ? (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.newsHorizontalList}
          >
            {filteredNews.map((item) => (
              <Pressable
                key={item.id}
                onPress={() =>
                  navigation.navigate('NewsDetail', {
                    newsId: item.id,
                    title: item.title,
                    category: item.category,
                    time: item.time,
                    body: item.body,
                    aiSummary: item.aiSummary,
                  })
                }
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
        ) : (
          <Text style={styles.emptyText}>검색 결과에 맞는 뉴스가 없습니다.</Text>
        )}
      </ScrollView>

      {/* Floating Bottom Tab Bar */}
      <View style={styles.bottomTab}>
        <Pressable style={styles.bottomTabItem}>
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
    gap: 12,
  },
  searchBar: {
    backgroundColor: colors.surface,
    borderRadius: 99,
    flex: 1,
    height: 44,
    justifyContent: 'center',
    paddingHorizontal: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  searchInput: {
    color: colors.text,
    fontSize: 14,
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
  tabBar: {
    borderBottomWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
    backgroundColor: colors.surface,
  },
  tabItem: {
    alignItems: 'center',
    flex: 1,
    paddingVertical: 14,
  },
  tabItemActive: {
    borderBottomWidth: 3,
    borderColor: colors.primary,
  },
  tabText: {
    color: colors.muted,
    fontSize: 15,
    fontWeight: '600',
  },
  tabTextActive: {
    color: colors.primary,
    fontWeight: '800',
  },
  content: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 90, // Buffer for floating bottom tab
  },
  chartCard: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    padding: 20,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 2,
    marginBottom: 16,
  },
  metricValue: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '800',
  },
  metricChange: {
    fontSize: 14,
    fontWeight: '700',
    marginTop: 4,
    marginBottom: 16,
  },
  chartContainer: {
    height: 120,
    width: '100%',
  },
  timeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
    paddingHorizontal: 8,
  },
  timeText: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: '500',
  },
  aiCard: {
    backgroundColor: colors.primarySoft,
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    gap: 8,
  },
  aiBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary,
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  aiBadgeText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: '800',
  },
  aiText: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '500',
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
  emptyText: {
    color: colors.muted,
    fontSize: 14,
    textAlign: 'center',
    marginTop: 20,
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
