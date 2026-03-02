import { ref } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'

export function useScrollReveal() {
  const target = ref(null)
  const isVisible = ref(false)

  useIntersectionObserver(target, ([{ isIntersecting }]) => {
    if (isIntersecting) {
      isVisible.value = true
    }
  }, { threshold: 0.1 })

  return { target, isVisible }
}
