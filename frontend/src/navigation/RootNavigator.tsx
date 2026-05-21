import { useEffect } from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';
import { StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
import { LearningRecordScreen } from '@/features/growth/screens/LearningRecordScreen';
import { getOnboardingStatus } from '@/features/onboarding/api';
import { OnboardingScreen } from '@/features/onboarding/screens/OnboardingScreen';
import { PromotionTestScreen } from '@/features/promotion-test/screens/PromotionTestScreen';
import { useUserStore } from '@/store/userStore';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
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
        profile: null,
        source: 'remote',
      });
    }
  }, [finishOnboarding, hasCompletedOnboarding, onboardingStatusQuery.data]);

  const isCheckingRemoteStatus =
    Boolean(accessToken) && !hasCompletedOnboarding && onboardingStatusQuery.isLoading;

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {isCheckingRemoteStatus ? (
        <Stack.Screen name="Onboarding">
          {() => (
            <View style={styles.loadingContainer}>
              <Text style={styles.loadingTitle}>기존 온보딩 상태를 확인하고 있어요</Text>
              <Text style={styles.loadingDescription}>
                서버에 이미 완료된 정보가 있으면 바로 학습 기록 화면으로 이어질게요.
              </Text>
            </View>
          )}
        </Stack.Screen>
      ) : hasCompletedOnboarding ? (
        <>
          <Stack.Screen name="Home" component={LearningRecordScreen} />
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
        </>
      ) : (
        <Stack.Screen name="Onboarding" component={OnboardingScreen} />
      )}
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
