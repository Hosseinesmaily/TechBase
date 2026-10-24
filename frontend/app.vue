<template>
  <NuxtLoadingIndicator
    color="#3479ff"
    error-color="#f87171"
    :height="3"
    :throttle="100"
    :duration="1200"
    :hide-delay="180"
  />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
