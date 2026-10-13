/**
 * Auth hook — проверка авторизации, редирект.
 * Depends on: authStore
 */

import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export function useAuth(requireAuth: boolean = true) {
  const navigate = useNavigate();
  const { isAuthenticated, user, checkAuth, token } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated && token) {
      checkAuth();
    }
  }, [isAuthenticated, token, checkAuth]);

  useEffect(() => {
    if (requireAuth && !isAuthenticated && !token) {
      navigate('/login', { replace: true });
    }
  }, [requireAuth, isAuthenticated, token, navigate]);

  return {
    isAuthenticated,
    user,
    token,
  };
}
