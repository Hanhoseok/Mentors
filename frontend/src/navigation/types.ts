export type AppStackParamList = {
  Login: undefined;
  Signup: undefined;
  Onboarding: undefined;
  Search: undefined;
  NewsDetail: {
    newsId: number;
    title: string;
    category: string;
    time: string;
    body: string;
    aiSummary: string;
  };
};

declare global {
  namespace ReactNavigation {
    // eslint-disable-next-line @typescript-eslint/no-empty-object-type
    interface RootParamList extends AppStackParamList {}
  }
}
