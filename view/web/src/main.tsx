import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@ant-design/v5-patch-for-react-19'
import './index.css'
import Login from './Login.tsx'
import Warning from './Warning.tsx'
import Capture from './Capture.tsx'

const root = createRoot(document.getElementById('root')!)

function renderRoute() {
  const hash = window.location.hash
  console.log('Current route hash:', hash)
  if (hash === '#/capture') {
    root.render(
      <StrictMode>
        <Capture />
      </StrictMode>
    )
  } else if (hash === '#/warning') {
    root.render(
      <StrictMode>
        <Warning />
      </StrictMode>
    )
  } else {
    root.render(
      <StrictMode>
        <Login />
      </StrictMode>
    )
  }
}

// 初始渲染
renderRoute()

// 当 hash 改变时重新渲染路由
window.addEventListener('hashchange', renderRoute)
