import { Component, type ReactNode } from 'react';
import { StatusBar } from 'expo-status-bar';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer, DefaultTheme, type Theme } from '@react-navigation/native';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/api/queryClient';
import { colors } from '@/constants/colors';
import { linking } from '@/navigation/linking';
import { HarnessNavigator } from '@/_dev-harness/HarnessNavigator';
import { RootNavigator } from '@/navigation/RootNavigator';

// -------------------------------------------------------------
// 진짜 프론트엔드를 개발/테스트할 때는 true로 설정합니다.
// false로 설정하면 백엔드 개발자들의 API 검증용 화면(harness)이 보입니다.
// -------------------------------------------------------------
const USE_REAL_FRONTEND = true;

// React Navigation 기본 테마 배경은 회색(rgb(242,242,242))이라, 플로팅 하단 탭
// 주변 여백으로 회색 박스처럼 비친다. 앱 배경색에 맞춰 덮어쓴다.
const navTheme: Theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    primary: colors.primary,
    text: colors.text,
  },
};

interface AppErrorBoundaryState {
  error: Error | null;
}

class AppErrorBoundary extends Component<{ children: ReactNode }, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = {
    error: null,
  };

  static getDerivedStateFromError(error: Error): AppErrorBoundaryState {
    return { error };
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <SafeAreaProvider>
        <ScrollView contentContainerStyle={styles.errorScrollContent}>
          <View style={styles.errorCard}>
            <Text style={styles.errorTitle}>화면을 불러오지 못했어요</Text>
            <Text style={styles.errorDescription}>
              테스트용 프론트엔드가 렌더링 중 예외로 멈췄습니다. 아래 메시지를 확인해 주세요.
            </Text>
            <Text selectable style={styles.errorMessage}>
              {this.state.error.message}
            </Text>
          </View>
        </ScrollView>
      </SafeAreaProvider>
    );
  }
}

export default function App() {
  return (
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SafeAreaProvider>
          <NavigationContainer linking={linking} theme={navTheme}>
            {USE_REAL_FRONTEND ? <RootNavigator /> : <HarnessNavigator />}
            {/* 배경이 항상 밝으므로 어두운 글자로 고정 (auto는 다크모드 기기에서 흰 글자가 됨) */}
            <StatusBar style="dark" />
          </NavigationContainer>
        </SafeAreaProvider>
      </QueryClientProvider>
    </AppErrorBoundary>
  );
}

const styles = StyleSheet.create({
  errorScrollContent: {
    backgroundColor: colors.background,
    flexGrow: 1,
    justifyContent: 'center',
    padding: 20,
  },
  errorCard: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    gap: 12,
    padding: 20,
  },
  errorTitle: {
    color: colors.rose,
    fontSize: 22,
    fontWeight: '800',
  },
  errorDescription: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 21,
  },
  errorMessage: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 20,
  },
});
