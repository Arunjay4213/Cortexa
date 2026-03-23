import { useState, useEffect } from 'react'

export function useStagger(inView: boolean, steps: number, ms = 420) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    if (!inView || step >= steps) return
    const t = setTimeout(() => setStep(s => s + 1), ms)
    return () => clearTimeout(t)
  }, [inView, step, steps, ms])
  return step
}
