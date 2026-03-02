<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center">
      <div class="absolute inset-0 bg-black/30" @click="$emit('cancel')" />
      <div class="relative bg-white border border-grey-200 rounded-xl shadow-card-hover p-4 w-80 z-10">
        <div class="text-subheading font-bold text-grey-900 mb-2">{{ title }}</div>
        <p class="text-body text-grey-700 mb-4">{{ message }}</p>
        <div class="flex gap-2 justify-end">
          <button
            class="text-caption px-3 py-1.5 rounded-lg border border-grey-300 text-grey-700 hover:bg-grey-100 transition-colors"
            @click="$emit('cancel')"
          >
            Cancel
          </button>
          <button
            class="text-caption px-3 py-1.5 rounded-lg bg-brand-primary text-white font-bold hover:bg-brand-dark transition-colors"
            @click="$emit('confirm')"
          >
            {{ confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: 'Confirm Action' },
  message: { type: String, default: 'Are you sure?' },
  confirmLabel: { type: String, default: 'Confirm' },
})

defineEmits(['confirm', 'cancel'])
</script>
