import { apiClient } from './client'

export type HealthResponse = {
  status: string
}

export const fetchHealth = async (): Promise<HealthResponse> => {
  const { data } = await apiClient.get<HealthResponse>('/health')
  return data
}
