import axios, { AxiosError } from 'axios';
import { useAuthStore } from '@/store/useAuthStore';

export const api = axios.create({
  baseURL: '',
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err: AxiosError<{ detail?: { error_class?: string; error_message?: string } }>) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().clear();
      const redirect = encodeURIComponent(window.location.pathname + window.location.search);
      window.location.href = `/login?redirect=${redirect}`;
    }
    return Promise.reject(err);
  },
);
