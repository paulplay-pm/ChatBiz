import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';

export interface Workflow {
  id: string;
  version: number;
  name: string;
  created_by: string;
  created_at: string;
  archived: boolean;
  definition_json: { mode?: string; sharing?: string; nodes?: unknown[]; edges?: unknown[]; variables?: Record<string, unknown> } | null;
  favorite?: boolean;
}

interface ListParams {
  search?: string;
  status?: string;
  type?: string;
  sharing?: string;
  page?: number;
  page_size?: number;
}

export function useWorkflows(params: ListParams) {
  return useQuery({
    queryKey: ['workflows', params],
    queryFn: async () => {
      const r = await api.get<{ workflows: Workflow[]; total: number }>('/workflows', { params });
      return r.data;
    },
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; definition_json: Workflow['definition_json']; mode?: string }) =>
      api.post<Workflow>('/workflows', body).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/workflows/${id}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  });
}

export function useToggleFavorite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, favorite }: { id: string; favorite: boolean }) =>
      api.patch(`/workflows/${id}/favorite`, { favorite }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  });
}
