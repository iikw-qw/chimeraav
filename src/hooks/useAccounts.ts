import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export interface AccountRow {
  id: string
  unique_code?: string | null
  device_id: string
  platform: string
  username: string
  status: string
  welcome_message_enabled: boolean
  auto_reply_enabled: boolean
  auto_chatter_language: string
}

export const ACCOUNTS_QUERY_KEY = ['accounts'] as const

async function fetchAccounts(): Promise<AccountRow[]> {
  const { data } = await api.get<AccountRow[]>('/api/accounts', {
    params: { limit: 200 },
  })
  return data
}

export function useAccounts() {
  return useQuery({
    queryKey: ACCOUNTS_QUERY_KEY,
    queryFn: fetchAccounts,
    staleTime: 30_000,
  })
}

export interface AccountCreatePayload {
  device_id: string
  platform: string
  username: string
  password_encrypted?: string | null
  auto_chatter_language?: string
  welcome_message_enabled?: boolean
}

export async function createAccount(payload: AccountCreatePayload): Promise<AccountRow> {
  const { data } = await api.post<AccountRow>('/api/accounts', payload)
  return data
}

export async function deleteAccount(accountId: string): Promise<void> {
  await api.delete(`/api/accounts/${accountId}`)
}

export interface AccountUpdatePayload {
  platform?: string
  username?: string
  password_encrypted?: string | null
  posting_style?: string
  auto_reply_enabled?: boolean
  welcome_message_enabled?: boolean
  auto_chatter_language?: string
  notify_new_messages?: boolean
  activity_hours_min?: number
  activity_hours_max?: number
  warmup_stage?: number
}

export async function updateAccount(
  accountId: string,
  payload: AccountUpdatePayload,
): Promise<AccountRow> {
  const { data } = await api.put<AccountRow>(`/api/accounts/${accountId}`, payload)
  return data
}

export interface AccountEmailInfo {
  email: string | null
  has_password: boolean
  imap_server: string | null
}

export async function getAccountEmail(accountId: string): Promise<AccountEmailInfo> {
  const { data } = await api.get<AccountEmailInfo>(`/api/accounts/${accountId}/email`)
  return data
}

export async function setAccountEmail(
  accountId: string,
  email: string,
  emailPassword: string,
): Promise<void> {
  await api.put(`/api/accounts/${accountId}/email`, {
    email,
    email_password: emailPassword,
  })
}

export async function fetchAuthCode(
  accountId: string,
): Promise<{ code: string }> {
  const { data } = await api.post<{ code: string }>(
    `/api/accounts/${accountId}/fetch-code`,
  )
  return data
}

export interface AutoLoginResponse {
  ok: boolean
  stage: string
  message: string
  account_id?: string
  device_id?: string
}

export async function autoLoginAccount(
  accountId: string,
  password?: string,
): Promise<AutoLoginResponse> {
  const { data } = await api.post<AutoLoginResponse>(
    `/api/accounts/${accountId}/auto-login`,
    { password: password ?? null },
  )
  return data
}
