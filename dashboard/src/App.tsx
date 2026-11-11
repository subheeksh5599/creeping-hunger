import { useEffect, useState } from "react"

import { Compare } from "@/pages/Compare"
import { Dashboard } from "@/pages/Dashboard"
import { Landing } from "@/pages/Landing"
import { ReviewDetail } from "@/pages/ReviewDetail"

function useHash() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const on = () => setHash(location.hash)
    addEventListener("hashchange", on)
    return () => removeEventListener("hashchange", on)
  }, [])
  return hash
}

export function App() {
  const hash = useHash()
  const review = hash.match(/^#\/review\/([\w-]+)/)
  if (review) return <ReviewDetail id={review[1]} />
  const compare = hash.match(/^#\/compare\/([\w-]+)\/([\w-]+)/)
  if (compare) return <Compare a={compare[1]} b={compare[2]} />
  if (hash.startsWith("#/dashboard")) return <Dashboard />
  return <Landing />
}

export default App
