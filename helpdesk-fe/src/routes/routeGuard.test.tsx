import { screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { Navigate, type RouteObject } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentUser } from '../api/auth'
import { renderRoutes } from '../test/render'
import { RedirectIfAuthenticated } from './RedirectIfAuthenticated'
import { RequireAuth } from './RequireAuth'
import { routes } from './routes'

// BE の API は呼ばず、応答を差し替える
vi.mock('../api/auth', () => ({
  login: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

/**
 * ログインしていなくても開けるページ。追加するときは、理由をここに書く。
 * - /login：ログインするための画面
 */
const PUBLIC_PATHS = ['/login']

type Page = {
  /** ページの URL（親の path とつないだもの） */
  path: string
  /** このページを表示するまでに通る element（親から順に、自分を含む） */
  elementTypes: unknown[]
}

const joinPath = (parent: string, child: string) =>
  child.startsWith('/') ? child : `${parent.replace(/\/$/, '')}/${child}`

/** 画面の一覧から、URL を持つページ（path か index のある route）をすべて集める */
const collectPages = (list: RouteObject[], parentPath = '', parentTypes: unknown[] = []): Page[] =>
  list.flatMap((route) => {
    const path = route.path === undefined ? parentPath : joinPath(parentPath, route.path)
    const elementTypes = route.element
      ? [...parentTypes, (route.element as ReactElement).type]
      : parentTypes
    const self = route.path !== undefined || route.index ? [{ path, elementTypes }] : []
    return [...self, ...collectPages(route.children ?? [], path, elementTypes)]
  })

/** すべての route（入れ子を含む） */
const allRoutes = (list: RouteObject[]): RouteObject[] =>
  list.flatMap((route) => [route, ...allRoutes(route.children ?? [])])

const pages = collectPages(routes)
const isCatchAll = (page: Page) => page.path.endsWith('*')
const isPublic = (page: Page) => PUBLIC_PATHS.includes(page.path)
const protectedPages = pages.filter((page) => !isCatchAll(page) && !isPublic(page))

/**
 * `:id` のような URL の変数を、仮の値に置き換える。
 * 省略できる部分（`:id?`・`edit?`）を使うときは、この置き換えも見直す
 */
const toUrl = (path: string) => path.replace(/:[^/]+/g, '1')

describe('画面の一覧の作り', () => {
  it('route は element で書く（Component・lazy では、ログインの確認を通るかをテストで確かめられないため）', () => {
    for (const route of allRoutes(routes)) {
      expect(route.Component).toBeUndefined()
      expect(route.lazy).toBeUndefined()
    }
  })

  it('route に、ログインの確認より先に動く処理や、確認の外で表示される画面を置かない', () => {
    // loader・action は RequireAuth の表示より先に動き、errorElement などは RequireAuth の外で表示される
    for (const route of allRoutes(routes)) {
      expect(route.loader, route.path).toBeUndefined()
      expect(route.action, route.path).toBeUndefined()
      expect(route.errorElement, route.path).toBeUndefined()
      expect(route.ErrorBoundary, route.path).toBeUndefined()
      expect(route.hydrateFallbackElement, route.path).toBeUndefined()
      expect(route.HydrateFallback, route.path).toBeUndefined()
    }
  })

  it('ログインの確認（RequireAuth）を通らないページは、PUBLIC_PATHS と、ほかのページに移るだけの URL だけ', () => {
    const unguarded = pages
      .filter((page) => !isCatchAll(page))
      .filter((page) => !page.elementTypes.includes(RequireAuth))
      .map((page) => page.path)

    expect([...unguarded].sort()).toEqual([...PUBLIC_PATHS].sort())
  })

  it('PUBLIC_PATHS 以外のページは、すべてログインの確認（RequireAuth）を通る', () => {
    expect(protectedPages.length).toBeGreaterThan(0)
    for (const page of protectedPages) {
      expect(page.elementTypes, page.path).toContain(RequireAuth)
    }
  })

  it('ログイン画面は、ログイン済みならチケット一覧に移る（RedirectIfAuthenticated）', () => {
    const loginPage = pages.find((page) => page.path === '/login')

    expect(loginPage?.elementTypes).toContain(RedirectIfAuthenticated)
  })

  it('そのほかの URL（*）は、ほかのページに移るだけか、ログインの確認を通る', () => {
    const catchAll = pages.filter(isCatchAll)

    expect(catchAll.length).toBeGreaterThan(0)
    for (const page of catchAll) {
      const onlyRedirects = page.elementTypes.length === 1 && page.elementTypes[0] === Navigate
      expect(onlyRedirects || page.elementTypes.includes(RequireAuth), page.path).toBe(true)
    }
  })
})

describe('ログインしていないとき（受け入れ要件 1）', () => {
  beforeEach(() => {
    vi.mocked(fetchCurrentUser).mockReset()
    vi.mocked(fetchCurrentUser).mockResolvedValue(null)
  })

  it.each([...protectedPages.map((page) => toUrl(page.path)), '/', '/not-found', '/tickets/x/y'])(
    '%s を開くと、ログイン画面に移る',
    async (url) => {
      const { router } = renderRoutes(url)

      expect(await screen.findByRole('heading', { name: 'ログイン' })).toBeInTheDocument()
      expect(router.state.location.pathname).toBe('/login')
    },
  )
})
