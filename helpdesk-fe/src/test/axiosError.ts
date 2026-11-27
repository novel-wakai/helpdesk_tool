import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'

/** BE が status の応答を返したときの Axios のエラー */
export const httpError = (status: number) => {
  const config = { headers: new AxiosHeaders() }
  const response: AxiosResponse = {
    status,
    statusText: '',
    headers: {},
    config,
    data: {},
  }
  return new AxiosError(
    `Request failed with status code ${status}`,
    'ERR_BAD_RESPONSE',
    config,
    null,
    response,
  )
}

/** BE に接続できなかったとき（応答がない）の Axios のエラー */
export const networkError = () => new AxiosError('Network Error', 'ERR_NETWORK')
