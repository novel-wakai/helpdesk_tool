import { useHealth } from '../../../hooks/useHealth'
import { Home, type ApiStatus } from '../presentational/Home'

export const HomeContainer = () => {
  const { isPending, isError } = useHealth()

  const apiStatus: ApiStatus = isPending ? 'checking' : isError ? 'error' : 'ok'

  return <Home apiStatus={apiStatus} />
}
