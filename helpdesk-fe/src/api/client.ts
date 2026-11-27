import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  // ログインの Cookie（HttpOnly。JavaScript からは読めない）を、API の呼び出しに付ける。
  // 画面は localhost で開く。127.0.0.1 で開けるようにしても、API が許可していない画面の URL に
  // なり（CORS）、API を呼べない。Cookie も SameSite=Strict のため、別のサイトとみなされて送られない
  withCredentials: true,
})
