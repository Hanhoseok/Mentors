import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import { colors } from '@/constants/colors';
import { AppIcon } from '@/components/AppIcon';
import type { AppStackParamList } from '@/navigation/types';
import { openInAppBrowser } from '@/utils';

type RouteProps = RouteProp<AppStackParamList, 'InAppBrowser'>;

/**
 * 앱 내부 WebView 브라우저.
 * 기사 화면과 동일한 레이아웃(상단 헤더 + 본문 영역)으로, 본문 영역에 원문을
 * 그대로 띄운다. 즉 "뉴스 내용이 보이던 그만큼의 크기"로 원문을 렌더링한다.
 */
export function InAppBrowserScreen() {
  const navigation = useNavigation();
  const route = useRoute<RouteProps>();
  const insets = useSafeAreaInsets();
  const { url, title } = route.params;

  const webRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);

  return (
    <SafeAreaView style={styles.screen} edges={['left', 'right', 'bottom']}>
      {/* 헤더 — 기사 화면과 동일한 높이/형태 */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Pressable onPress={() => navigation.goBack()} style={styles.iconBtn} hitSlop={8}>
          <Text style={styles.backArrow}>←</Text>
        </Pressable>
        <Text numberOfLines={1} style={styles.headerTitle}>
          {title ?? '원문 기사'}
        </Text>
        <Pressable
          onPress={() => void openInAppBrowser(url)}
          style={styles.iconBtn}
          hitSlop={8}
        >
          <AppIcon color={colors.primary} name="open-in-new" size={20} />
        </Pressable>
      </View>

      {/* 로딩 진행 바 */}
      {loading ? (
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${Math.round(progress * 100)}%` }]} />
        </View>
      ) : null}

      <View style={styles.webWrap}>
        <WebView
          ref={webRef}
          source={{ uri: url }}
          startInLoadingState
          onLoadProgress={({ nativeEvent }) => setProgress(nativeEvent.progress)}
          onLoadStart={() => setLoading(true)}
          onLoadEnd={() => setLoading(false)}
          renderLoading={() => (
            <View style={styles.center}>
              <ActivityIndicator color={colors.primary} />
            </View>
          )}
          // 안드로이드에서 일부 페이지가 about:blank로 떨어지는 것 방지
          setSupportMultipleWindows={false}
          allowsBackForwardNavigationGestures
          decelerationRate={Platform.OS === 'ios' ? 'normal' : undefined}
        />
      </View>
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
    gap: 8,
    minHeight: 56,
    paddingBottom: 12,
    paddingHorizontal: 12,
  },
  iconBtn: {
    alignItems: 'center',
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  backArrow: {
    color: colors.text,
    fontSize: 22,
  },
  headerTitle: {
    color: colors.text,
    flex: 1,
    fontSize: 16,
    fontWeight: '800',
  },
  progressTrack: {
    backgroundColor: colors.border,
    height: 2,
    width: '100%',
  },
  progressFill: {
    backgroundColor: colors.primary,
    height: 2,
  },
  webWrap: {
    flex: 1,
  },
  center: {
    alignItems: 'center',
    backgroundColor: colors.background,
    flex: 1,
    justifyContent: 'center',
  },
});
