import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
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
  Empty
} from 'antd'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons'
import { buildApiUrl, API_ENDPOINTS } from '../config/api'
import { formatTimestamp } from '../utils/dateUtils'
import './CoverageDetail.css'

const { Title, Text } = Typography

function CoverageDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [files, setFiles] = useState([])
  const [treeData, setTreeData] = useState([])
  const [selectedFile, setSelectedFile] = useState(null)
  const [coverageData, setCoverageData] = useState(null)
  const [fileContent, setFileContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [fileListLoading, setFileListLoading] = useState(false)
  const [error, setError] = useState(null)
  const [editor, setEditor] = useState(null)
  const [decorations, setDecorations] = useState([])
  const [expandedKeys, setExpandedKeys] = useState([])
  const [selectedKeys, setSelectedKeys] = useState([])

  useEffect(() => {
    fetchReportDetail()
    fetchFileList()
  }, [id])

  useEffect(() => {
    if (selectedFile) {
      fetchFileCoverage(selectedFile)
    }
  }, [selectedFile, report])

  useEffect(() => {
    if (editor && coverageData && fileContent) {
      applyCoverageDecorations()
    }
  }, [editor, coverageData, fileContent])

  const fetchReportDetail = async () => {
    try {
      setLoading(true)
      const response = await axios.get(buildApiUrl(API_ENDPOINTS.REPORT_DETAIL(id)))
      setReport(response.data.report)
      setError(null)
    } catch (err) {
      setError(err.message || '获取报告详情失败')
      console.error('Error fetching report detail:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchFileList = async () => {
    try {
      setFileListLoading(true)
      const response = await axios.get(buildApiUrl(`${API_ENDPOINTS.FILES}?report_id=${id}`))
      const fileList = response.data.data || []
      setFiles(fileList)
      
      // 构建树状数据
      const tree = buildTreeData(fileList)
      setTreeData(tree)
      
      // 默认展开根节点
      const rootKeys = tree.map(node => node.key)
      setExpandedKeys(rootKeys)
      
      // 默认选中第一个文件
      if (fileList.length > 0) {
        const firstFile = fileList[0]
        setSelectedFile(firstFile)
        setSelectedKeys([`file-${firstFile.id}`])
      }
    } catch (err) {
      console.error('Error fetching file list:', err)
    } finally {
      setFileListLoading(false)
    }
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

  const buildTreeData = (files) => {
    const treeMap = {}
    const roots = []

    files.forEach(file => {
      if (!file.file) return
      
      const pathParts = file.file.split('/').filter(part => part.length > 0)
      if (pathParts.length === 0) return
      
      let currentPath = ''
      let parentKey = null
      
      pathParts.forEach((part, index) => {
        const isFile = index === pathParts.length - 1
        const key = isFile ? `file-${file.id}` : `dir-${currentPath}/${part}`
        const fullPath = currentPath ? `${currentPath}/${part}` : part
        
        if (!treeMap[key]) {
          const coverageRate = isFile ? (file.coverage_rate ?? 0) : null
          const node = {
            key,
            title: part,
            isLeaf: isFile,
            file: isFile ? file : null,
            coverageRate: coverageRate,
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
    if (info.node.isLeaf && info.node.file) {
      setSelectedFile(info.node.file)
      setSelectedKeys(selectedKeys)
    }
  }

  const onExpand = (expandedKeys) => {
    setExpandedKeys(expandedKeys)
  }

  const fetchFileCoverage = async (file) => {
    if (!file || !file.id) return
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await axios.get(buildApiUrl(API_ENDPOINTS.FILE_DETAIL(file.id)))
      setCoverageData(response.data)
      
      if (report) {
        try {
          // 兼容repo和repo_url两个字段（后端返回的是repo_url）
          const repoUrl = report.repo_url || report.repo
          
          if (!repoUrl) {
            console.error('[CoverageDetail] ❌ report中缺少repo_url字段:', report)
            setFileContent(generatePlaceholderContent(response.data.ranges))
            return
          }
          
          const repoMatch = repoUrl.match(/([^/]+)\.git$/)
          const repoName = repoMatch ? repoMatch[1] : repoUrl.split('/').pop().replace('.git', '')
          
          console.log('[CoverageDetail] 正在获取文件内容:', {
            repo: repoName,
            commit: report.commit,
            path: file.file,
            fullRepoUrl: repoUrl
          })
          
          const fileContentResponse = await axios.get(buildApiUrl('/api/coverage/file'), {
            params: {
              repo: repoName,
              commit: report.commit,
              path: file.file
            }
          })
          
          console.log('[CoverageDetail] 文件内容API响应:', {
            hasContent: !!fileContentResponse.data?.content,
            contentLength: fileContentResponse.data?.content?.length || 0,
            responseData: fileContentResponse.data
          })
          
          if (fileContentResponse.data && fileContentResponse.data.content) {
            setFileContent(fileContentResponse.data.content)
            console.log('[CoverageDetail] ✅ 成功设置真实文件内容')
          } else {
            console.warn('[CoverageDetail] ⚠️ API返回空内容，使用placeholder')
            setFileContent(generatePlaceholderContent(response.data.ranges))
          }
        } catch (err) {
          console.warn('[CoverageDetail] ❌ 获取文件内容失败，使用placeholder:', err)
          console.warn('[CoverageDetail] 错误详情:', {
            message: err.message,
            response: err.response?.data,
            status: err.response?.status
          })
          setFileContent(generatePlaceholderContent(response.data.ranges))
        }
      } else {
        console.warn('[CoverageDetail] ⚠️ report对象为空，使用placeholder')
        setFileContent(generatePlaceholderContent(response.data.ranges))
      }
    } catch (err) {
      setError(err.message || '获取文件覆盖率失败')
      console.error('Error fetching file coverage:', err)
      setCoverageData(null)
      setFileContent('')
    } finally {
      setLoading(false)
    }
  }

  const generatePlaceholderContent = (ranges) => {
    if (!ranges || ranges.length === 0) {
      return '// 暂无代码内容'
    }

    const maxLine = Math.max(...ranges.map(r => r.endLine))
    const lines = []
    
    for (let i = 1; i <= maxLine; i++) {
      lines.push(`// Line ${i}`)
    }
    
    return lines.join('\n')
  }

  const handleEditorDidMount = (editor, monaco) => {
    setEditor(editor)
    window.monaco = monaco
    
    monaco.editor.defineTheme('coverage-theme', {
      base: 'vs',
      inherit: true,
      rules: [],
      colors: {
        'editor.background': '#ffffff',
      }
    })
    
    monaco.editor.setTheme('coverage-theme')
  }

  const applyCoverageDecorations = () => {
    if (!editor || !coverageData || !coverageData.ranges) {
      return
    }

    const monaco = window.monaco
    if (!monaco) {
      return
    }

    const newDecorations = coverageData.ranges.map((range) => {
      const { startLine, endLine, startCol, endCol, hit } = range
      
      const startLineNum = Math.max(1, startLine)
      const endLineNum = Math.max(1, endLine)
      
      const isUncovered = hit === 0
      const gutterColor = isUncovered ? '#f44336' : '#4caf50'
      
      return {
        range: new monaco.Range(
          startLineNum,
          startCol || 1,
          endLineNum,
          endCol || 1000
        ),
        options: {
          isWholeLine: true,
          inlineClassName: `coverage-decoration-${isUncovered ? 'red' : 'green'}`,
          glyphMarginClassName: `coverage-gutter-${isUncovered ? 'red' : 'green'}`,
          minimap: {
            color: gutterColor,
            position: 1
          },
          overviewRuler: {
            color: gutterColor,
            position: 2
          },
          hoverMessage: {
            value: `命中次数: ${hit}`
          },
          inlineClassNameAffectsLetterSpacing: true
        }
      }
    })

    const decorationIds = editor.deltaDecorations(decorations, newDecorations.map(d => ({
      range: d.range,
      options: d.options
    })))
    
    setDecorations(decorationIds)
  }

  const rangeColumns = [
    {
      title: '起始行',
      dataIndex: 'startLine',
      key: 'startLine',
      width: 100,
      align: 'center'
    },
    {
      title: '起始列',
      dataIndex: 'startCol',
      key: 'startCol',
      width: 100,
      align: 'center'
    },
    {
      title: '结束行',
      dataIndex: 'endLine',
      key: 'endLine',
      width: 100,
      align: 'center'
    },
    {
      title: '结束列',
      dataIndex: 'endCol',
      key: 'endCol',
      width: 100,
      align: 'center'
    },
    {
      title: 'Statements',
      dataIndex: 'statements',
      key: 'statements',
      width: 120,
      align: 'center',
      render: (text) => text ?? '-'
    },
    {
      title: '执行次数',
      dataIndex: 'hit',
      key: 'hit',
      width: 120,
      align: 'center'
    },
    {
      title: '状态',
      key: 'status',
      width: 120,
      align: 'center',
      render: (_, record) => (
        record.hit === 0 ? (
          <Tag color="error" icon={<CloseCircleOutlined />}>未覆盖</Tag>
        ) : (
          <Tag color="success" icon={<CheckCircleOutlined />}>已覆盖</Tag>
        )
      )
    }
  ]

  if (loading && !report) {
    return (
      <div className="coverage-detail-container">
        <Card>
          <Spin size="large" tip="加载中..." />
        </Card>
      </div>
    )
  }

  if (error && !report) {
    return (
      <div className="coverage-detail-container">
        <Card>
          <Alert
            message="错误"
            description={error}
            type="error"
            showIcon
            action={
              <Button onClick={() => navigate('/')}>
                返回列表
              </Button>
            }
          />
        </Card>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="coverage-detail-container">
        <Card>
          <Empty description="未找到数据" />
        </Card>
      </div>
    )
  }

  const totalStatements = coverageData?.total_statements ?? selectedFile?.total_statements ?? 0
  const coveredStatements = coverageData?.covered_statements ?? selectedFile?.covered_statements ?? 0
  const coverageRate = coverageData?.coverage_rate ?? selectedFile?.coverage_rate ?? 0

  return (
    <div className="coverage-detail-container">
      <Card>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 头部信息 */}
          <div>
            <Space style={{ marginBottom: 12 }}>
              <Button
                icon={<ArrowLeftOutlined />}
                onClick={() => navigate('/')}
              >
                返回列表
              </Button>
            </Space>
            <Title level={3} style={{ margin: 0, fontFamily: 'monospace' }}>
              {report.repo} - {report.branch}
            </Title>
            <Divider style={{ margin: '8px 0' }} />
            <Descriptions column={{ xs: 1, sm: 2, md: 3 }} size="small">
              <Descriptions.Item label="Commit">
                <Text code>{report.commit}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="初始上报时间">
                {formatTimestamp(report.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="最新上报时间">
                {formatTimestamp(report.updated_at)}
              </Descriptions.Item>
            </Descriptions>
          </div>

          <Divider style={{ margin: '8px 0' }} />

          {/* 主要内容区域 */}
          <Row gutter={16}>
            {/* 左侧文件列表 */}
            <Col xs={24} sm={24} md={8} lg={6}>
              <Card
                title="文件列表"
                size="small"
                style={{ height: 'calc(100vh - 200px)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
                bodyStyle={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', padding: '12px' }}
              >
                {fileListLoading ? (
                  <Spin tip="加载中..." />
                ) : files.length === 0 ? (
                  <Empty description="暂无文件" />
                ) : (
                  <div style={{ flex: 1, overflow: 'auto' }}>
                    <Tree
                      showLine
                      showIcon
                      treeData={treeData.map(node => ({
                        ...node,
                        title: node.isLeaf ? (
                          <Space>
                            <FileTextOutlined />
                            <Text>{node.title}</Text>
                            {node.coverageRate !== null && getCoverageTag(node.coverageRate)}
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
                  <Empty description="请从左侧选择一个文件查看覆盖率详情" />
                </Card>
              ) : loading ? (
                <Card>
                  <Spin size="large" tip="加载中..." />
                </Card>
              ) : error ? (
                <Card>
                  <Alert
                    message="错误"
                    description={error}
                    type="error"
                    showIcon
                  />
                </Card>
              ) : !coverageData ? (
                <Card>
                  <Empty description="未找到覆盖率数据" />
                </Card>
              ) : (
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  {/* 文件信息和统计 */}
                  <Card size="small">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <Title level={4} style={{ margin: 0, fontFamily: 'monospace', wordBreak: 'break-all' }}>
                        {coverageData.file}
                      </Title>
                      <Row gutter={16}>
                        <Col xs={24} sm={8}>
                          <Statistic
                            title="总有效行"
                            value={totalStatements}
                            valueStyle={{ color: '#1890ff' }}
                          />
                        </Col>
                        <Col xs={24} sm={8}>
                          <Statistic
                            title="已覆盖行"
                            value={coveredStatements}
                            valueStyle={{ color: '#52c41a' }}
                          />
                        </Col>
                        <Col xs={24} sm={8}>
                          <Statistic
                            title="覆盖率"
                            value={coverageRate}
                            precision={2}
                            suffix="%"
                            valueStyle={{
                              color: coverageRate >= 80 ? '#52c41a' : coverageRate >= 50 ? '#faad14' : '#ff4d4f'
                            }}
                          />
                        </Col>
                      </Row>
                      <Divider style={{ margin: '8px 0' }} />
                      <Space>
                        <Tag color="error">
                          <span className="legend-color red"></span>
                          未覆盖 (hit = 0)
                        </Tag>
                        <Tag color="success">
                          <span className="legend-color green"></span>
                          已覆盖 (hit > 0)
                        </Tag>
                      </Space>
                    </Space>
                  </Card>

                  {/* 代码编辑器 */}
                  <Card title="代码内容" size="small">
                    <div className="editor-container">
                      <Editor
                        height="calc(100vh - 500px)"
                        language="go"
                        value={fileContent}
                        theme="coverage-theme"
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
                  </Card>

                  {/* 覆盖率范围详情 */}
                  <Card title="覆盖率范围详情" size="small">
                    <Table
                      columns={rangeColumns}
                      dataSource={coverageData.ranges?.map((range, index) => ({
                        ...range,
                        key: index
                      }))}
                      pagination={{
                        pageSize: 10,
                        showSizeChanger: true,
                        showQuickJumper: true,
                        showTotal: (total) => `共 ${total} 条记录`
                      }}
                      rowClassName={(record) => record.hit === 0 ? 'uncovered-row' : 'covered-row'}
                      size="small"
                    />
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

export default CoverageDetail
