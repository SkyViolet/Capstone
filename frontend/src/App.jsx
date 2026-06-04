import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import client from './api/client'

const CATEGORIES = ['식비', '카페·간식', '교통', '문화·생활', '주거·통신', '기타']

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

function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}

// ─── 인증 모달 (로그인 / 회원가입 탭) ──────────────────────
function AuthModal({ initialMode = 'login', onClose, onLoginSuccess }) {
  const [mode, setMode] = useState(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const overlayRef = useRef(null)

  // 탭 전환 시 에러 초기화
  function switchMode(m) {
    setMode(m)
    setError('')
  }

  // 오버레이 클릭 시 닫기
  function handleOverlayClick(e) {
    if (e.target === overlayRef.current) onClose()
  }

  async function handleLogin(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    try {
      const { data } = await client.post('/login', form.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('token', data.access_token)
      onLoginSuccess(data.access_token)
    } catch {
      setError('이메일 또는 비밀번호가 틀렸습니다.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSignup(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await client.post('/signup', { email, password })
      // 가입 완료 → 로그인 탭으로 전환 (이메일 유지)
      switchMode('login')
    } catch (err) {
      setError(err.response?.data?.detail || '회원가입에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" ref={overlayRef} onClick={handleOverlayClick}>
      <div className="modal-card" role="dialog" aria-modal="true">
        <button className="modal-close" onClick={onClose} aria-label="닫기">✕</button>

        {/* 탭 전환 */}
        <div className="modal-tabs">
          <button
            className={`modal-tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => switchMode('login')}
          >
            로그인
          </button>
          <button
            className={`modal-tab ${mode === 'signup' ? 'active' : ''}`}
            onClick={() => switchMode('signup')}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={mode === 'login' ? handleLogin : handleSignup}>
          <input
            type="email"
            placeholder="이메일"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="비밀번호"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? <><Spinner /> {mode === 'login' ? '로그인 중…' : '가입 중…'}</> : (mode === 'login' ? '로그인' : '가입하기')}
          </button>
        </form>

        <p className="modal-switch">
          {mode === 'login' ? (
            <>계정이 없으신가요?{' '}
              <button className="link-btn" onClick={() => switchMode('signup')}>회원가입</button>
            </>
          ) : (
            <>이미 계정이 있으신가요?{' '}
              <button className="link-btn" onClick={() => switchMode('login')}>로그인</button>
            </>
          )}
        </p>
      </div>
    </div>
  )
}

// ─── 메인 앱 ───────────────────────────────────────────────
export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '')
  const [expenses, setExpenses] = useState([])
  const [toast, setToast] = useState(null)

  const [uploading, setUploading] = useState(false)
  const [categorizingId, setCategorizingId] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [newExp, setNewExp] = useState({ item_name: '', amount: '', category: '식비' })

  // 인증 모달 제어
  const [authModal, setAuthModal] = useState(null) // null | 'login' | 'signup'

  const loggedIn = useMemo(() => Boolean(token), [token])

  // 로그인 상태 변경 시 지출 목록 자동 로드
  useEffect(() => {
    if (loggedIn) loadExpenses()
    else setExpenses([])
  }, [loggedIn]) // eslint-disable-line react-hooks/exhaustive-deps

  function showToast(msg, type = 'info') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  // 로그인이 필요한 액션 — 비로그인 시 모달 오픈
  function guard(fn) {
    if (!loggedIn) {
      setAuthModal('login')
      return
    }
    fn()
  }

  function handleLoginSuccess(newToken) {
    setToken(newToken)
    setAuthModal(null)
    showToast('로그인 성공!')
  }

  function logout() {
    localStorage.removeItem('token')
    setToken('')
    showToast('로그아웃되었습니다.')
  }

  // ─ API 함수 ─

  async function loadExpenses() {
    try {
      const { data } = await client.get('/expenses')
      setExpenses(data)
    } catch {
      showToast('지출 목록 조회 실패', 'error')
    }
  }

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

  return (
    <div className="app">
      {/* ─ 헤더 ─ */}
      <header className="app-header">
        <span className="header-title">💳 SpendWise</span>
        {loggedIn ? (
          <button className="btn-ghost" onClick={logout}>로그아웃</button>
        ) : (
          <div className="header-auth">
            <button className="btn-ghost" onClick={() => setAuthModal('login')}>로그인</button>
            <button className="btn-outline" onClick={() => setAuthModal('signup')}>회원가입</button>
          </div>
        )}
      </header>

      <main className="app-main">
        {/* ─ 요약 카드 ─ */}
        {loggedIn ? (
          <div className="summary-card">
            <p className="summary-label">이번 달 총 지출</p>
            <p className="summary-amount">{totalAmount.toLocaleString()}원</p>
            <p className="summary-count">{expenses.length}건</p>
          </div>
        ) : (
          <div className="welcome-card">
            <p className="welcome-emoji">💳</p>
            <h2 className="welcome-title">AI SpendWise</h2>
            <p className="welcome-desc">영수증을 찍으면 AI가 알아서<br />카테고리를 분류하고 소비를 분석해드려요</p>
            <button className="btn-primary welcome-cta" onClick={() => setAuthModal('signup')}>
              무료로 시작하기
            </button>
          </div>
        )}

        {/* ─ 빠른 액션 버튼 3종 ─ */}
        <div className="action-row">
          {/* 영수증 촬영: 비로그인 시 모달 오픈, 로그인 시 카메라 직접 실행 */}
          {loggedIn ? (
            <label className="action-btn btn-camera" aria-disabled={uploading}>
              {uploading ? <Spinner /> : <span className="action-icon">📷</span>}
              <span>{uploading ? '처리 중…' : '영수증 촬영'}</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={uploadReceipt}
                disabled={uploading}
              />
            </label>
          ) : (
            <button className="action-btn btn-camera" onClick={() => setAuthModal('login')}>
              <span className="action-icon">📷</span>
              <span>영수증 촬영</span>
            </button>
          )}

          <button
            className="action-btn btn-add"
            onClick={() => guard(() => setShowAddForm((v) => !v))}
          >
            <span className="action-icon">{showAddForm ? '✕' : '+'}</span>
            <span>직접 입력</span>
          </button>

          <button
            className="action-btn btn-refresh"
            onClick={() => guard(loadExpenses)}
          >
            <span className="action-icon">↻</span>
            <span>새로고침</span>
          </button>
        </div>

        {/* ─ 수동 지출 입력 폼 ─ */}
        {showAddForm && loggedIn && (
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

        {/* ─ 지출 내역 ─ */}
        <div>
          <h2 className="section-title">지출 내역</h2>
          {!loggedIn ? (
            <div className="empty-state" onClick={() => setAuthModal('login')} style={{ cursor: 'pointer' }}>
              <p>🔒</p>
              <p>로그인하면 지출 내역을 볼 수 있어요</p>
            </div>
          ) : expenses.length === 0 ? (
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

      {/* ─ 인증 모달 ─ */}
      {authModal && (
        <AuthModal
          initialMode={authModal}
          onClose={() => setAuthModal(null)}
          onLoginSuccess={handleLoginSuccess}
        />
      )}

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  )
}
