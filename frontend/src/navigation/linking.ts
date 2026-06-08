import { type LinkingOptions } from '@react-navigation/native';
import * as ExpoLinking from 'expo-linking';
import type { AppStackParamList } from './types';

export const linking: LinkingOptions<AppStackParamList> = {
  prefixes: [ExpoLinking.createURL('/'), 'mentors://'],
  config: {
    screens: {
      MainTabs: {
        screens: {
          DebateArena: 'debate',
          MentorChat: 'mentor-chat',
        },
      },
      PromotionTest: 'promotion-test',
      DailyReportDetail: {
        path: 'report/:reportId',
        parse: {
          reportId: (value: string) => Number(value),
        },
      },
    },
  },
};
