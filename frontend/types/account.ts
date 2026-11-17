export interface AccountResponse {
  authenticated?: boolean
  user?: {
    id: number
    email: string
    name: string
    is_staff: boolean
  } | null
  csrf_token?: string
  error?: string
}
