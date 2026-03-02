import { ref } from 'vue'

const toastRef = ref(null)

export function setToastRef(ref) {
  toastRef.value = ref
}

export function useToast() {
  return {
    success(title, message = '', { duration = 3000, action = null } = {}) {
      toastRef.value?.add('success', title, message, duration, action)
    },
    error(title, message = '', { duration = 3000, action = null } = {}) {
      toastRef.value?.add('error', title, message, duration, action)
    },
    warning(title, message = '', { duration = 3000, action = null } = {}) {
      toastRef.value?.add('warning', title, message, duration, action)
    },
    info(title, message = '', { duration = 3000, action = null } = {}) {
      toastRef.value?.add('info', title, message, duration, action)
    },
  }
}
