import { Modal, Form, Input, Radio, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useCreateWorkflow } from '@/hooks/useWorkflows';

interface FormValues {
  name: string;
  mode: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateWorkflowModal({ open, onClose }: Props) {
  const [form] = Form.useForm<FormValues>();
  const navigate = useNavigate();
  const create = useCreateWorkflow();

  const onFinish = async (values: FormValues) => {
    try {
      const wf = await create.mutateAsync({
        name: values.name,
        mode: values.mode,
        definition_json: { nodes: [], edges: [], variables: {}, mode: values.mode },
      });
      message.success('已创建工作流');
      form.resetFields();
      onClose();
      navigate(`/workflows/${wf.id}/edit?version=${wf.version}`);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: { error_message?: string } } } };
      message.error(err.response?.data?.detail?.error_message ?? '创建失败');
    }
  };

  return (
    <Modal title="新建工作流" open={open} onCancel={onClose} onOk={() => form.submit()} confirmLoading={create.isPending}>
      <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ mode: 'workflow' }}>
        <Form.Item label="名称" name="name" rules={[{ required: true, message: '名称必填' }]}>
          <Input placeholder="例:paul 财务月报" autoFocus />
        </Form.Item>
        <Form.Item label="类型" name="mode" rules={[{ required: true }]}>
          <Radio.Group>
            <Radio.Button value="workflow">Workflow(单次)</Radio.Button>
            <Radio.Button value="chatflow">Chatflow(多轮)</Radio.Button>
          </Radio.Group>
        </Form.Item>
      </Form>
    </Modal>
  );
}
