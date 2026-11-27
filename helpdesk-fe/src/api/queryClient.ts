import { hashKey, MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'

/** ログイン中のユーザーを保持するキー */
export const currentUserQueryKey = ['auth', 'me'] as const

// 取得に失敗したときに、やり直す回数の上限
const MAX_RETRIES = 3

/**
 * 取得に失敗したとき、やり直すか。
 * BE が 4xx（401：ログインが切れた、403：権限がない、404：ないなど）を返したときは、
 * やり直しても結果が変わらないため、やり直さない（401 ならすぐにログイン画面に移れるように）。
 */
export const shouldRetry = (failureCount: number, error: unknown) => {
  const status = isAxiosError(error) ? error.response?.status : undefined
  if (status !== undefined && status >= 400 && status < 500) {
    return false
  }
  return failureCount < MAX_RETRIES
}

/**
 * ログイン中のユーザー以外の、取得したデータをすべて消す。
 * ログインが切れたときや、別のユーザーでログインし直したときに、前のユーザーのデータを
 * 表示しないようにする。
 */
export const clearUserData = (queryClient: QueryClient) => {
  const currentUserHash = hashKey(currentUserQueryKey)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== currentUserHash })
}

/**
 * アプリ全体で使う QueryClient を作る。
 *
 * どの API でも 401（ログインが切れた）が返ったら、取得したデータを消し、ログイン中のユーザーを
 * 「なし」にする。ログインが必要な画面はそれを見て、ログイン画面に移る（JWT の有効期限切れなど）。
 */
export const createQueryClient = () => {
  const queryClient: QueryClient = new QueryClient({
    defaultOptions: { queries: { retry: shouldRetry } },
    queryCache: new QueryCache({ onError: (error) => clearUserOnUnauthorized(error) }),
    mutationCache: new MutationCache({ onError: (error) => clearUserOnUnauthorized(error) }),
  })

  const clearUserOnUnauthorized = (error: unknown) => {
    if (isAxiosError(error) && error.response?.status === 401) {
      clearUserData(queryClient)
      queryClient.setQueryData(currentUserQueryKey, null)
    }
  }

  return queryClient
}
