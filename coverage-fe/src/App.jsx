import React from 'react'
import { Routes, Route, Link, useLocation } from 'react-router-dom'
import CoverageList from './components/CoverageList'
import CoverageDetail from './components/CoverageDetail'
import DiffCoverageDetail from './components/DiffCoverageDetail'
import ConfigManagement from './components/ConfigManagement'
import './App.css'

function App() {
  const location = useLocation()

  return (
    <div className="app">
      <header className="app-header">
        <div className="container">
          <h1>覆盖率数据展示平台</h1>
          <nav>
            <Link 
              to="/" 
              className={location.pathname === '/' ? 'active' : ''}
            >
              覆盖率列表
            </Link>
            <Link 
              to="/config/go" 
              className={location.pathname.startsWith('/config') ? 'active' : ''}
            >
              配置管理
            </Link>
          </nav>
        </div>
      </header>
      <main className="app-main">
        <div className="container">
          <Routes>
            <Route path="/" element={<CoverageList />} />
            <Route path="/detail/:id" element={<CoverageDetail />} />
            <Route path="/diff/:id" element={<DiffCoverageDetail />} />
            <Route path="/config/go" element={<ConfigManagement language="go" />} />
            <Route path="/config/java" element={<ConfigManagement language="java" />} />
            <Route path="/config/python" element={<ConfigManagement language="python" />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export default App

