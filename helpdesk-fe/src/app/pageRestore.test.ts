import { afterEach, describe, expect, it, vi } from 'vitest'

import { protectPageOnRestore } from './pageRestore'

const pageEvent = (type: 'pagehide' | 'pageshow', persisted: boolean) =>
  Object.assign(new Event(type), { persisted }) as PageTransitionEvent

let stop: () => void = () => {}

afterEach(() => {
  stop()
  document.documentElement.style.visibility = ''
})

describe('protectPageOnRestore', () => {
  it('画面を離れるときにメモリに残される場合は、ページ全体（トーストなど #root の外も含む）を隠す', () => {
    // #root の外（Portal）に表示されるトースト
    const toast = document.createElement('div')
    document.body.appendChild(toast)
    stop = protectPageOnRestore(vi.fn())

    window.dispatchEvent(pageEvent('pagehide', true))

    expect(document.documentElement.style.visibility).toBe('hidden')
    expect(toast).not.toBeVisible()
    toast.remove()
  })

  it('メモリに残されない場合は、表示を隠さない', () => {
    stop = protectPageOnRestore(vi.fn())

    window.dispatchEvent(pageEvent('pagehide', false))

    expect(document.documentElement.style.visibility).toBe('')
  })

  it('メモリから復元されたら、ページを読み込み直す（ログインの状態を確かめ直す）', () => {
    const reload = vi.fn()
    stop = protectPageOnRestore(reload)

    window.dispatchEvent(pageEvent('pageshow', true))

    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('普通に画面を開いたとき（復元ではない）は、読み込み直さない', () => {
    const reload = vi.fn()
    stop = protectPageOnRestore(reload)

    window.dispatchEvent(pageEvent('pageshow', false))

    expect(reload).not.toHaveBeenCalled()
  })

  it('監視をやめたあとは、何もしない', () => {
    const reload = vi.fn()
    protectPageOnRestore(reload)()

    window.dispatchEvent(pageEvent('pagehide', true))
    window.dispatchEvent(pageEvent('pageshow', true))

    expect(document.documentElement.style.visibility).toBe('')
    expect(reload).not.toHaveBeenCalled()
  })
})
