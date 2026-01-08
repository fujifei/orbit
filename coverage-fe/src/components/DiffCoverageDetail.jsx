import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom'
import Editor from '@monaco-editor/react'
import axios from 'axios'
import {
  Card,
  Typography,
  Space,
  Tag,
  Statistic,
  Row,
  Col,
  Tree,
  Table,
  Button,
  Spin,
  Alert,
  Divider,
  Descriptions,
  Empty,
  Breadcrumb
} from 'antd'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  RiseOutlined,
  FallOutlined,
  HomeOutlined
} from '@ant-design/icons'
import { buildApiUrl, API_ENDPOINTS } from '../config/api'
import { formatTimestamp } from '../utils/dateUtils'
import './DiffCoverageDetail.css'

const { Title, Text } = Typography

// 根据coverage_format判断语言类型
const getLanguageFromCoverageFormat = (coverageFormat) => {
  if (!coverageFormat) return 'go' // 默认为go
  const format = coverageFormat.toLowerCase()
  if (format === 'goc' || format === 'go') return 'go'
  if (format === 'java' || format === 'jacoco') return 'java'
  if (format === 'python' || format === 'coverage' || format === 'pyca' || format === 'pca') return 'python'
  return 'go' // 默认
}

function DiffCoverageDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [report, setReport] = useState(null)
  const [diffData, setDiffData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [language, setLanguage] = useState(null) // 语言类型
  
  // 文件树相关状态
  const [treeData, setTreeData] = useState([])
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [fileLoading, setFileLoading] = useState(false)
  const [expandedKeys, setExpandedKeys] = useState([])
  const [selectedKeys, setSelectedKeys] = useState([])
  
  // Monaco Editor 相关
  const [editor, setEditor] = useState(null)
  const [decorations, setDecorations] = useState([])

  useEffect(() => {
    fetchReportDetail()
    fetchDiffCoverage()
  }, [id])
  
  useEffect(() => {
    if (selectedFile && report) {
      fetchFileContent(selectedFile)
    }
  }, [selectedFile, report])
  
  useEffect(() => {
    if (editor && selectedFile && fileContent && diffData) {
      applyDiffCoverageDecorations()
    }
  }, [editor, selectedFile, fileContent, diffData])

  const fetchReportDetail = async () => {
    try {
      const response = await axios.get(buildApiUrl(API_ENDPOINTS.REPORT_DETAIL(id)))
      const reportData = response.data.report
      setReport(reportData)
      
      // 从URL参数获取语言，如果没有则从report的coverage_format判断
      const langFromUrl = searchParams.get('lang')
      if (langFromUrl && ['go', 'java', 'python'].includes(langFromUrl)) {
        setLanguage(langFromUrl)
      } else {
        setLanguage(getLanguageFromCoverageFormat(reportData.coverage_format))
      }
      
      setError(null)
    } catch (err) {
      setError(err.message || '获取报告详情失败')
      console.error('Error fetching report detail:', err)
    }
  }

  const fetchDiffCoverage = async () => {
    try {
      setLoading(true)
      const response = await axios.get(buildApiUrl(API_ENDPOINTS.DIFF_COVERAGE(id)))
      setDiffData(response.data)
      setError(null)
      
      // 构建文件树
      const files = response.data.files || []
      if (files.length > 0) {
        const tree = buildTreeData(files)
        setTreeData(tree)
        
        // 默认展开根节点
        const rootKeys = tree.map(node => node.key)
        setExpandedKeys(rootKeys)
        
        // 默认选中第一个文件
        const firstFile = files[0]
        setSelectedFile(firstFile)
        setSelectedKeys([`file-${firstFile.file}`])
      }
    } catch (err) {
      setError(err.message || '获取增量覆盖率失败')
      console.error('Error fetching diff coverage:', err)
    } finally {
      setLoading(false)
    }
  }
  
  const buildTreeData = (files) => {
    const treeMap = {}
    const roots = []

    files.forEach((file, index) => {
      if (!file.file) return
      
      const pathParts = file.file.split('/').filter(part => part.length > 0)
      if (pathParts.length === 0) return
      
      let currentPath = ''
      let parentKey = null
      
      pathParts.forEach((part, idx) => {
        const isFile = idx === pathParts.length - 1
        const key = isFile ? `file-${file.file}` : `dir-${currentPath}/${part}`
        const fullPath = currentPath ? `${currentPath}/${part}` : part
        
        if (!treeMap[key]) {
          const node = {
            key,
            title: part,
            isLeaf: isFile,
            fileData: isFile ? file : null,
            children: []
          }
          
          treeMap[key] = node
          
          if (parentKey) {
            treeMap[parentKey].children.push(node)
          } else {
            roots.push(node)
          }
        }
        
        parentKey = key
        currentPath = fullPath
      })
    })
    
    return roots
  }
  
  const onSelect = (selectedKeys, info) => {
    if (info.node.isLeaf && info.node.fileData) {
      setSelectedFile(info.node.fileData)
      setSelectedKeys(selectedKeys)
    }
  }

  const onExpand = (expandedKeys) => {
    setExpandedKeys(expandedKeys)
  }
  
  const fetchFileContent = async (fileData) => {
    if (!fileData || !report) return
    
    try {
      setFileLoading(true)
      
      // 兼容repo和repo_url两个字段（后端返回的是repo_url）
      const repoUrl = report.repo_url || report.repo
      
      if (!repoUrl) {
        console.error('[DiffCoverageDetail] ❌ report中缺少repo_url字段:', report)
        setFileContent('// 无法获取文件内容：缺少仓库URL')
        setFileLoading(false)
        return
      }
      
      const repoMatch = repoUrl.match(/([^/]+)\.git$/)
      const repoName = repoMatch ? repoMatch[1] : repoUrl.split('/').pop().replace('.git', '')
      
      console.log('[DiffCoverageDetail] 正在获取文件内容:', {
        repo: repoName,
        commit: report.commit,
        path: fileData.file,
        fullRepoUrl: repoUrl
      })
      
      const response = await axios.get(buildApiUrl('/api/coverage/file'), {
        params: {
          repo: repoName,
          commit: report.commit,
          path: fileData.file
        }
      })
      
      console.log('[DiffCoverageDetail] 文件内容API响应:', {
        hasContent: !!response.data?.content,
        contentLength: response.data?.content?.length || 0,
        responseData: response.data
      })
      
      if (response.data && response.data.content) {
        setFileContent(response.data.content)
        console.log('[DiffCoverageDetail] ✅ 成功设置真实文件内容')
      } else {
        console.warn('[DiffCoverageDetail] ⚠️ API返回空内容')
        setFileContent('// 无法获取文件内容')
      }
    } catch (err) {
      console.warn('[DiffCoverageDetail] ❌ 获取文件内容失败:', err)
      console.warn('[DiffCoverageDetail] 错误详情:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      })
      setFileContent('// 无法获取文件内容')
    } finally {
      setFileLoading(false)
    }
  }
  
  const handleEditorDidMount = (editor, monaco) => {
    setEditor(editor)
    window.monaco = monaco
    
    monaco.editor.defineTheme('diff-coverage-theme', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#ffffff',
      }
    })
    
    monaco.editor.setTheme('diff-coverage-theme')
  }
  
  const applyDiffCoverageDecorations = () => {
    if (!editor || !selectedFile || !diffData) {
      return
    }

    const monaco = window.monaco
    if (!monaco) {
      return
    }

    const lines = selectedFile.lines || []
    
    console.log('[DiffCoverageDetail] 应用装饰:', {
      file: selectedFile.file,
      linesCount: lines.length,
      sampleLine: lines[0]
    })
    
    const newDecorations = lines.map((lineData) => {
      // 兼容两种字段名：line 和 line_number
      const lineNumber = lineData.line || lineData.line_number
      const status = lineData.status
      const hit = lineData.hit
      
      if (!lineNumber || !status) {
        console.warn('[DiffCoverageDetail] ⚠️ 跳过无效行数据:', lineData)
        return null
      }
      
      let className = ''
      let gutterColor = ''
      let statusText = ''
      
      switch(status) {
        case 'new_covered':
          className = 'diff-coverage-new-covered'
          gutterColor = '#52c41a'
          statusText = '新增已覆盖'
          break
        case 'new_uncovered':
          className = 'diff-coverage-new-uncovered'
          gutterColor = '#ff4d4f'
          statusText = '新增未覆盖'
          break
        case 'coverage_improved':
          className = 'diff-coverage-improved'
          gutterColor = '#1890ff'
          statusText = '覆盖提升'
          break
        case 'coverage_degraded':
          className = 'diff-coverage-degraded'
          gutterColor = '#faad14'
          statusText = '覆盖退化'
          break
        default:
          console.warn('[DiffCoverageDetail] ⚠️ 未知状态:', status)
          return null
      }
      
      return {
        range: new monaco.Range(lineNumber, 1, lineNumber, 1),
        options: {
          isWholeLine: true,
          inlineClassName: className,
          glyphMarginClassName: `coverage-gutter-${status}`,
          minimap: {
            color: gutterColor,
            position: 1
          },
          overviewRuler: {
            color: gutterColor,
            position: 2
          },
          hoverMessage: {
            value: `${statusText} - 执行次数: ${hit}`
          }
        }
      }
    }).filter(d => d !== null)
    
    console.log('[DiffCoverageDetail] 生成装饰数量:', newDecorations.length)

    const decorationIds = editor.deltaDecorations(decorations, newDecorations.map(d => ({
      range: d.range,
      options: d.options
    })))
    
    setDecorations(decorationIds)
  }

  const getStatusTag = (status) => {
    const statusConfig = {
      'new_covered': { color: 'success', icon: <CheckCircleOutlined />, text: '新增已覆盖' },
      'new_uncovered': { color: 'error', icon: <CloseCircleOutlined />, text: '新增未覆盖' },
      'coverage_improved': { color: 'processing', icon: <RiseOutlined />, text: '覆盖提升' },
      'coverage_degraded': { color: 'warning', icon: <FallOutlined />, text: '覆盖退化' }
    }
    
    const config = statusConfig[status] || { color: 'default', text: status }
    return <Tag color={config.color} icon={config.icon}>{config.text}</Tag>
  }

  const getCoverageTag = (rate) => {
    if (rate === null || rate === undefined) return <Tag>-</Tag>
    const value = parseFloat(rate)
    if (value >= 80) {
      return <Tag color="success">{value.toFixed(2)}%</Tag>
    } else if (value >= 50) {
      return <Tag color="warning">{value.toFixed(2)}%</Tag>
    } else {
      return <Tag color="error">{value.toFixed(2)}%</Tag>
    }
  }
  
  const getFileSummary = (fileData) => {
    if (!fileData || !fileData.summary) return null
    
    const summary = fileData.summary
    const total = summary.new_covered + summary.new_uncovered
    const rate = total > 0 ? (summary.new_covered / total * 100) : 0
    
    return {
      total,
      rate,
      summary
    }
  }

  if (loading) {
    return (
      <div className="diff-coverage-detail-container">
        <Card>
          <Spin size="large" tip="加载中..." />
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="diff-coverage-detail-container">
        <Card>
          <Alert
            message="错误"
            description={error}
            type="error"
            showIcon
            action={
              <Button onClick={() => navigate(`/?lang=${language || 'go'}`)}>
                返回列表
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (!diffData || !diffData.summary) {
    return (
      <div className="diff-coverage-detail-container">
        <Card>
          <Empty description="暂无增量覆盖率数据" />
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Button onClick={() => navigate(`/?lang=${language || 'go'}`)}>
              返回列表
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  const summary = diffData.summary
  const fileSummary = selectedFile ? getFileSummary(selectedFile) : null

  return (
    <div className="diff-coverage-detail-container">
      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 头部信息 */}
          <div>
            {/* 面包屑导航 */}
            <Breadcrumb style={{ marginBottom: 12 }}>
              <Breadcrumb.Item>
                <Link to="/">
                  <HomeOutlined /> 首页
                </Link>
              </Breadcrumb.Item>
              <Breadcrumb.Item>
                <Link to={`/?lang=${language || 'go'}`}>
                  Data - {language === 'java' ? 'JAVA' : language === 'python' ? 'Python' : 'GO'}
                </Link>
              </Breadcrumb.Item>
              <Breadcrumb.Item>增量覆盖率详情</Breadcrumb.Item>
            </Breadcrumb>
            
            <Space style={{ marginBottom: 12 }}>
              <Button
                icon={<ArrowLeftOutlined />}
                onClick={() => navigate(`/?lang=${language || 'go'}`)}
              >
                返回列表
              </Button>
            </Space>
            <Title level={3} style={{ margin: 0, fontFamily: 'monospace' }}>
              {report?.repo} - {report?.branch} (增量覆盖率)
            </Title>
            <Divider style={{ margin: '8px 0' }} />
            <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
              <Descriptions.Item label="目标 Commit">
                <Text code>{diffData.target_commit}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="基准 Commit">
                <Text code>{diffData.base_commit}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="基准分支">
                <Tag color="blue">{diffData.base_branch}</Tag>
              </Descriptions.Item>
              {report && (
                <>
                  <Descriptions.Item label="初始上报时间">
                    {formatTimestamp(report.created_at)}
                  </Descriptions.Item>
                  <Descriptions.Item label="最新上报时间">
                    {formatTimestamp(report.updated_at)}
                  </Descriptions.Item>
                </>
              )}
            </Descriptions>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          {/* 总体统计 */}
          <Row gutter={16}>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="增量覆盖率"
                value={summary.incremental_coverage_rate || 0}
                precision={2}
                suffix="%"
                valueStyle={{
                  color: summary.incremental_coverage_rate >= 80 ? '#52c41a' : 
                         summary.incremental_coverage_rate >= 60 ? '#faad14' : '#ff4d4f'
                }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="新增已覆盖"
                value={summary.new_covered_lines || 0}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="新增未覆盖"
                value={summary.new_uncovered_lines || 0}
                valueStyle={{ color: '#ff4d4f' }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="覆盖提升"
                value={summary.coverage_improved_lines || 0}
                valueStyle={{ color: '#1890ff' }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="覆盖退化"
                value={summary.coverage_degraded_lines || 0}
                valueStyle={{ color: '#faad14' }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="影响文件"
                value={summary.total_files || 0}
                valueStyle={{ color: '#1890ff' }}
              />
            </Col>
          </Row>

          <Divider style={{ margin: '8px 0' }} />

          {/* 主要内容区域 */}
          <Row gutter={16}>
            {/* 左侧文件列表 */}
            <Col xs={24} sm={24} md={8} lg={6}>
              <Card
                title="文件列表"
                size="small"
                style={{ height: 'calc(100vh - 320px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
                bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: '12px' }}
              >
                {treeData.length === 0 ? (
                  <Empty description="暂无文件" />
                ) : (
                  <div style={{ flex: 1, overflow: 'auto' }}>
                    <Tree
                      showLine
                      showIcon
                      treeData={treeData.map(node => ({
                        ...node,
                        title: node.isLeaf ? (
                          <Space size="small">
                            <FileTextOutlined />
                            <Text style={{ fontSize: '13px' }}>{node.title}</Text>
                          </Space>
                        ) : node.title
                      }))}
                      expandedKeys={expandedKeys}
                      selectedKeys={selectedKeys}
                      onSelect={onSelect}
                      onExpand={onExpand}
                    />
                  </div>
                )}
              </Card>
            </Col>

            {/* 右侧覆盖率详情 */}
            <Col xs={24} sm={24} md={16} lg={18}>
              {!selectedFile ? (
                <Card>
                  <Empty description="请从左侧选择一个文件查看增量覆盖率详情" />
                </Card>
              ) : (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  {/* 文件信息和统计 */}
                  <Card size="small">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Title level={4} style={{ margin: 0, fontFamily: 'monospace', wordBreak: 'break-all' }}>
                        {selectedFile.file}
                      </Title>
                      {fileSummary && (
                        <Row gutter={16}>
                          <Col xs={24} sm={6}>
                            <Statistic
                              title="新增已覆盖"
                              value={fileSummary.summary.new_covered}
                              valueStyle={{ color: '#52c41a', fontSize: '20px' }}
                            />
                          </Col>
                          <Col xs={24} sm={6}>
                            <Statistic
                              title="新增未覆盖"
                              value={fileSummary.summary.new_uncovered}
                              valueStyle={{ color: '#ff4d4f', fontSize: '20px' }}
                            />
                          </Col>
                          <Col xs={24} sm={6}>
                            <Statistic
                              title="覆盖提升"
                              value={fileSummary.summary.coverage_improved}
                              valueStyle={{ color: '#1890ff', fontSize: '20px' }}
                            />
                          </Col>
                          <Col xs={24} sm={6}>
                            <Statistic
                              title="覆盖退化"
                              value={fileSummary.summary.coverage_degraded}
                              valueStyle={{ color: '#faad14', fontSize: '20px' }}
                            />
                          </Col>
                        </Row>
                      )}
                      <Divider style={{ margin: '8px 0' }} />
                      <Space wrap>
                        {getStatusTag('new_covered')}
                        {getStatusTag('new_uncovered')}
                        {getStatusTag('coverage_improved')}
                        {getStatusTag('coverage_degraded')}
                      </Space>
                    </Space>
                  </Card>

                  {/* 代码编辑器 */}
                  <Card title="代码内容" size="small">
                    {fileLoading ? (
                      <Spin tip="加载文件内容..." />
                    ) : (
                      <div className="editor-container">
                        <Editor
                          height="calc(100vh - 550px)"
                          language="go"
                          value={fileContent}
                          theme="diff-coverage-theme"
                          onMount={handleEditorDidMount}
                          options={{
                            readOnly: true,
                            minimap: { enabled: true },
                            glyphMargin: true,
                            lineNumbers: 'on',
                            scrollBeyondLastLine: false,
                            wordWrap: 'on',
                          }}
                        />
                      </div>
                    )}
                  </Card>
                </Space>
              )}
            </Col>
          </Row>
        </Space>
      </Card>
    </div>
  )
}

export default DiffCoverageDetail

