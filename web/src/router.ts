import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/HomeView.vue') },
    { path: '/enroll', component: () => import('./views/EnrollView.vue') },
    { path: '/checkin', component: () => import('./views/CheckInView.vue') },
    { path: '/care', component: () => import('./views/CareView.vue') },
  ],
})
