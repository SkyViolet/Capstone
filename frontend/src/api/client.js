import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 토큰 만료(60분) 등 401 응답 시: 죽은 토큰을 정리하고 앱에 알려 로그인 모달을 띄웁니다.
// (로그인 실패는 400이라서 이 분기에 걸리지 않습니다)
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && localStorage.getItem('token')) {
      localStorage.removeItem('token')
      window.dispatchEvent(new Event('auth:unauthorized'))
    }
    return Promise.reject(error)
  }
)

export default client
