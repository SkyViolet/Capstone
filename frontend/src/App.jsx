import { useEffect, useMemo, useState } from 'react'
import './App.css'
import client from './api/client'

const CATEGORIES = ['식비', '카페·간식', '교통', '문화·생활', '주거·통신', '기타']

// 카테고리별 배지 색상 — 시각적으로 바로 구분되도록 고정
const CAT_COLOR = {
  '식비': '#f97316',
  '카페·간식': '#92400e',
  '교통': '#3b82f6',
  '문화·생활': '#8b5cf6',
  '주거·통신': '#10b981',
  '기타': '#6b7280',
}

function Badge({ category }) {
  return (
    <span className="badge" style={{ background: CAT_COLOR[category] ?? '#6b7280' }}>
      {category || '미분류'}
    </span>
  )
}

// CSS 스피너 — 버튼 안에 inline으로 사용
function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}

export default function App() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [expenses, setExpenses] = useState([])
  const [toast, setToast] = useState(null)

  // 업로드/분류/폼 제출 각각 독립 로딩 상태
  const [uploading, setUploading] = useState(false)
  const [categorizingId, setCategorizingId] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newExp, setNewExp] = useState({ item_name: '', amount: '', category: '식비' })

  const loggedIn = useMemo(() => Boolean(token), [token])

  // 로그인 상태가 바뀔 때(= 로그인 성공 직후) 지출 목록 자동 로드
  useEffect(() => {
    if (loggedIn) loadExpenses()
  }, [loggedIn]) // eslint-disable-line react-hooks/exhaustive-deps

  // Toast: 3초 후 자동 소멸
  function showToast(msg, type = 'info') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // --- API 호출 ---

  async function loadExpenses() {
    try {
      const { data } = await client.get('/expenses')
      setExpenses(data)
    } catch {
      showToast('지출 목록 조회 실패', 'error')
    }
  }

  async function login(e) {
    e.preventDefault()
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    try {
      const { data } = await client.post('/login', form.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('token', data.access_token)
      setToken(data.access_token) // → useEffect가 loadExpenses 호출
    } catch {
      showToast('이메일 또는 비밀번호가 틀렸습니다.', 'error')
    }
  }

  function logout() {
    localStorage.removeItem('token')
    setToken('')
    setExpenses([])
  }

  // capture="environment" — 후면 카메라 직접 실행 (iOS Safari 지원)
  async function uploadReceipt(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      await client.post('/expenses/from-receipt', formData)
      showToast('영수증 등록 완료!')
      await loadExpenses()
    } catch {
      showToast('영수증 처리 실패', 'error')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function addExpense(e) {
    e.preventDefault()
    setSubmitting(true)
    try {
      await client.post('/expenses', {
        item_name: newExp.item_name,
        amount: Number(newExp.amount),
        category: newExp.category,
      })
      showToast('지출 등록 완료!')
      setNewExp({ item_name: '', amount: '', category: '식비' })
      setShowAddForm(false)
      await loadExpenses()
    } catch {
      showToast('지출 등록 실패', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  async function autoCategorize(expenseId) {
    setCategorizingId(expenseId)
    try {
      const { data } = await client.post(`/expenses/${expenseId}/auto-categorize`)
      showToast(`${data.expense.category} — ${data.comment}`)
      await loadExpenses()
    } catch {
      showToast('자동 분류 실패', 'error')
    } finally {
      setCategorizingId(null)
    }
  }

  async function deleteExpense(id) {
    try {
      await client.delete(`/expenses/${id}`)
      setExpenses((prev) => prev.filter((e) => e.id !== id))
      showToast('삭제 완료')
    } catch {
      showToast('삭제 실패', 'error')
    }
  }

  const totalAmount = useMemo(
    () => expenses.reduce((sum, e) => sum + e.amount, 0),
    [expenses]
  )

  // --- 렌더링 ---

  if (!loggedIn) {
    return (
      <div className="login-screen">
        <div className="login-hero">
          <div className="login-logo">💳</div>
          <h1>AI SpendWise</h1>
          <p>영수증 촬영으로 스마트하게 관리하는 가계부</p>
        </div>
        <form className="login-form" onSubmit={login}>
          <input
            type="email"
            placeholder="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="비밀번호"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="btn-primary">로그인</button>
        </form>
        {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="header-title">💳 SpendWise</span>
        <button className="btn-ghost" onClick={logout}>로그아웃</button>
      </header>

      <main className="app-main">
        {/* 이번 달 총 지출 요약 카드 */}
        <div className="summary-card">
          <p className="summary-label">이번 달 총 지출</p>
          <p className="summary-amount">{totalAmount.toLocaleString()}원</p>
          <p className="summary-count">{expenses.length}건</p>
        </div>

        {/* 빠른 액션 버튼 3종 */}
        <div className="action-row">
          <label className="action-btn btn-camera" aria-disabled={uploading}>
            {uploading ? <Spinner /> : <span className="action-icon">📷</span>}
            <span>{uploading ? '처리 중…' : '영수증 촬영'}</span>
            {/* capture="environment" — 후면 카메라 직접 실행 */}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              onChange={uploadReceipt}
              disabled={uploading}
            />
          </label>

          <button
            className="action-btn btn-add"
            onClick={() => setShowAddForm((v) => !v)}
          >
            <span className="action-icon">{showAddForm ? '✕' : '+'}</span>
            <span>직접 입력</span>
          </button>

          <button className="action-btn btn-refresh" onClick={loadExpenses}>
            <span className="action-icon">↻</span>
            <span>새로고침</span>
          </button>
        </div>

        {/* 수동 지출 입력 폼 */}
        {showAddForm && (
          <form className="card add-form" onSubmit={addExpense}>
            <h3 className="form-title">지출 추가</h3>
            <input
              type="text"
              placeholder="항목 (예: 편의점, 버스카드)"
              value={newExp.item_name}
              onChange={(e) => setNewExp({ ...newExp, item_name: e.target.value })}
              required
            />
            <input
              type="number"
              placeholder="금액 (원)"
              value={newExp.amount}
              onChange={(e) => setNewExp({ ...newExp, amount: e.target.value })}
              required
              min="1"
              inputMode="numeric"
            />
            <select
              value={newExp.category}
              onChange={(e) => setNewExp({ ...newExp, category: e.target.value })}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? <><Spinner /> 등록 중…</> : '등록'}
            </button>
          </form>
        )}

        {/* 지출 내역 목록 */}
        <div>
          <h2 className="section-title">지출 내역</h2>
          {expenses.length === 0 ? (
            <div className="empty-state">
              <p>📝</p>
              <p>영수증을 촬영하거나 직접 입력해보세요</p>
            </div>
          ) : (
            <ul className="expense-list">
              {expenses.map((exp) => (
                <li key={exp.id} className="expense-item">
                  <div className="expense-left">
                    <Badge category={exp.category} />
                    <p className="expense-name">{exp.item_name}</p>
                    {exp.is_ocr && <span className="ocr-tag">OCR</span>}
                  </div>
                  <div className="expense-right">
                    <p className="expense-amount">{exp.amount.toLocaleString()}원</p>
                    <div className="expense-actions">
                      {/* AI 자동 분류 — 분류 중일 때 스피너 표시 */}
                      <button
                        className="icon-btn"
                        onClick={() => autoCategorize(exp.id)}
                        disabled={categorizingId === exp.id}
                        title="AI 자동 분류"
                        aria-label="AI 자동 분류"
                      >
                        {categorizingId === exp.id ? <Spinner /> : '🤖'}
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => deleteExpense(exp.id)}
                        title="삭제"
                        aria-label="삭제"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
