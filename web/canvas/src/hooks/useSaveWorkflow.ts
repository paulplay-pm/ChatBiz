import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/apiClient';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { useToast } from 'ui/primitives/Toast';

export function useSaveWorkflow() {
  const qc = useQueryClient();
  const { workflowId, nodes, edges, markClean, setInitial } = useCanvasEditStore();
  const toast = useToast();

  return useMutation({
    mutationFn: async (overrides?: { name?: string }) => {
      if (!workflowId) {
        const r = await api.post('/workflows', {
          name: overrides?.name || '未命名工作流',
          definition_json: { nodes, edges, mode: 'workflow' },
        });
        return r.data;
      } else {
        const r = await api.put(`/workflows/${workflowId}`, {
          definition_json: { nodes, edges, mode: 'workflow' },
        });
        return r.data;
      }
    },
    onSuccess: (data: any) => {
      markClean();
      toast.info('已保存');
      qc.invalidateQueries({ queryKey: ['workflows'] });
      if (!workflowId && data?.id) {
        // newly created: refresh store + let caller navigate
        setInitial(data.id, data.version ?? 1, nodes, edges);
      } else if (data?.version) {
        // updated: bump version
        useCanvasEditStore.setState({ version: data.version });
      }
      return data;
    },
    onError: (e: any) => {
      toast.error(e.response?.data?.detail?.error_message || '保存失败');
    },
  });
}
