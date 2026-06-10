import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';

interface NodeSchema {
  type: string;
  version: string;
  config_schema: any;
}

export function useNodeSchema(type: string | null) {
  return useQuery({
    queryKey: ['node-schema', type],
    queryFn: async () => {
      if (!type) return null;
      const r = await api.get<NodeSchema>(`/api/nodes/${type}/schema`);
      return r.data;
    },
    enabled: !!type,
    staleTime: 5 * 60 * 1000,
  });
}
