import { apiClient } from '@/api/client';
import type { DailyReportCard } from '@/features/learning/types';

export async function getDailyReport(reportId: number): Promise<DailyReportCard> {
  const response = await apiClient.get<DailyReportCard>(`/api/daily-report/${reportId}`);
  return response.data;
}

export async function listMyReports(limit = 20): Promise<DailyReportCard[]> {
  const response = await apiClient.get<DailyReportCard[]>('/api/daily-report/me/history', {
    params: { limit },
  });
  return response.data;
}
