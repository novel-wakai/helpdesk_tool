import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  // チェック対象外（ビルド結果やテストの出力）
  globalIgnores(['dist', 'coverage', 'playwright-report', 'test-results']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended, // JavaScript の基本ルール
      tseslint.configs.recommended, // TypeScript の基本ルール
      reactHooks.configs.flat.recommended, // React のフックの正しい使い方
      reactRefresh.configs.vite, // Vite のコード変更の自動反映（HMR）を壊さない書き方
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  // 書式は Prettier に任せる（ESLint 側の書式ルールを無効化して、両者がぶつからないようにする）
  prettier,
])
