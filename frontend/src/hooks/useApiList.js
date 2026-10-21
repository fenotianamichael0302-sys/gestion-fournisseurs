import { useCallback, useEffect, useState } from 'react'
import { api, getErrorMessage } from '../api/client'

export default function useApiList(endpoint, query = {}) {
  const [rows, setRows] = useState([])
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [count, setCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadCount, setReloadCount] = useState(0)
  const queryKey = JSON.stringify(query)

  useEffect(() => {
    const controller = new AbortController()
    setIsLoading(true)
    setError('')
    api.get(`/${endpoint}/`, {
      params: {
        page,
        ...(search ? { search } : {}),
        ...JSON.parse(queryKey),
      },
      signal: controller.signal,
    })
      .then(({ data }) => {
        if (Array.isArray(data)) {
          setRows(data)
          setCount(data.length)
        } else {
          setRows(data.results || [])
          setCount(data.count || 0)
        }
      })
      .catch((requestError) => {
        if (requestError.code !== 'ERR_CANCELED') {
          setError(getErrorMessage(requestError))
          setRows([])
          setCount(0)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })
    return () => controller.abort()
  }, [endpoint, page, queryKey, reloadCount, search])

  const refresh = useCallback(() => setReloadCount((countValue) => countValue + 1), [])
  const changeSearch = useCallback((value) => {
    setPage(1)
    setSearch(value)
  }, [])
  const changePage = useCallback((value) => setPage(value), [])

  return {
    rows,
    page,
    setPage: changePage,
    search,
    setSearch: changeSearch,
    count,
    isLoading,
    error,
    refresh,
  }
}
