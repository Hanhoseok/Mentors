import { useEffect } from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
import { getOnboardingStatus } from '@/features/onboarding/api';
import { useUserStore } from '@/store/userStore';
import { buildCompletedProfileFromStatus } from './onboarding/logic';
import { DevLoginScreen } from './screens/DevLoginScreen';
import { MainTabNavigator } from './MainTabNavigator';
import { InterestSettingsScreen } from './screens/InterestSettingsScreen';
import { OnboardingScreen } from './screens/OnboardingScreen';
import { PromotionTestScreen } from './screens/PromotionTestScreen';
import { resolveEntryScreenState } from './navigation/logic';
import type { RootStackParamList } from './navigation/types';

const Stack = createNativeStackNavigator<RootStackParamList>();

function LoadingScreen() {
  return (
    <View style={styles.loadingContainer}>
      <Text style={styles.loadingTitle}>기존 온보딩 상태를 확인하고 있어요.</Text>
      <Text style={styles.loadingDescription}>
        서버에 저장된 온보딩 정보가 있으면 바로 학습 기록 화면으로 이어집니다.
      </Text>
    </View>
  );
}

export function HarnessNavigator() {
  const accessToken = useUserStore((state) => state.accessToken);
  const hasCompletedOnboarding = useUserStore((state) => state.hasCompletedOnboarding);
  const finishOnboarding = useUserStore((state) => state.finishOnboarding);
  const onboardingStatusQuery = useQuery({
    queryKey: ['onboarding-status', accessToken],
    queryFn: getOnboardingStatus,
    enabled: Boolean(accessToken) && !hasCompletedOnboarding,
    retry: 0,
  });

  useEffect(() => {
    if (onboardingStatusQuery.data?.onboarded && !hasCompletedOnboarding) {
      finishOnboarding({
        profile: buildCompletedProfileFromStatus(onboardingStatusQuery.data),
        source: 'remote',
      });
    }
  }, [finishOnboarding, hasCompletedOnboarding, onboardingStatusQuery.data]);

  const isCheckingRemoteStatus =
    Boolean(accessToken) && !hasCompletedOnboarding && onboardingStatusQuery.isLoading;

  const entryScreenState = resolveEntryScreenState({
    accessToken,
    hasCompletedOnboarding,
    isCheckingRemoteStatus,
  });

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {entryScreenState === 'checking' ? (
        <Stack.Screen name="Onboarding" component={LoadingScreen} />
      ) : null}

      {entryScreenState === 'login' ? (
        <Stack.Screen name="Login" component={DevLoginScreen} />
      ) : null}

      {entryScreenState === 'onboarding' ? (
        <Stack.Screen name="Onboarding" component={OnboardingScreen} />
      ) : null}

      {entryScreenState === 'home' ? (
        <>
          <Stack.Screen name="Home" component={MainTabNavigator} />
          <Stack.Screen
            name="PromotionTest"
            component={PromotionTestScreen}
            options={{
              headerShown: true,
              title: '승급시험',
              headerShadowVisible: false,
              headerStyle: { backgroundColor: colors.background },
              headerTintColor: colors.text,
            }}
          />
          <Stack.Screen
            name="InterestSettings"
            component={InterestSettingsScreen}
            options={{ animation: 'slide_from_right' }}
          />
        </>
      ) : null}
    </Stack.Navigator>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    backgroundColor: colors.background,
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  loadingTitle: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 12,
  },
  loadingDescription: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 22,
  },
});
