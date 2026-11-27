/**
 * ブラウザの「戻る」「進む」で、前の画面がメモリからそのまま復元される（bfcache）ときの対策。
 *
 * 復元された画面は、離れたときの状態（ログアウトする前のチケット一覧など）のままで、
 * ログインの状態も確かめ直されない。共用の PC で、前の人のデータが見えてしまわないように、
 * - 画面を離れるとき（メモリに残される場合）は、ページ全体を隠しておく。#root の外に表示される
 *   トーストやダイアログ（Portal）も隠すため、<html> ごと隠す
 * - 復元されたときは、ページを読み込み直す（BE にログインの状態を確かめ直し、データも取り直す）
 *
 * ただし、スワイプで戻るときのプレビューなど、ブラウザ自身が撮った画面の画像は防げない。
 * データを守るのは、BE の権限の確認である。
 *
 * ログインしたままの人も、戻る・進むで画面が読み込み直される（入力中の内容は残らない）。
 *
 * @returns 監視をやめる関数
 */
export const protectPageOnRestore = (
  reload: () => void = () => window.location.reload(),
  target: Window = window,
) => {
  const handlePageHide = (event: PageTransitionEvent) => {
    if (event.persisted) {
      document.documentElement.style.visibility = 'hidden'
    }
  }
  const handlePageShow = (event: PageTransitionEvent) => {
    if (event.persisted) {
      reload()
    }
  }
  target.addEventListener('pagehide', handlePageHide)
  target.addEventListener('pageshow', handlePageShow)
  return () => {
    target.removeEventListener('pagehide', handlePageHide)
    target.removeEventListener('pageshow', handlePageShow)
  }
}
