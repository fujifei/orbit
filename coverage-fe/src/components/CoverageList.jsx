import React, { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  Layout,
  Menu,
  Table,
  Card,
  Form,
  Input,
  DatePicker,
  Button,
  Space,
  Tag,
  Typography,
  message,
  Row,
  Col,
  Divider
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  EyeOutlined,
  DatabaseOutlined,
  FileTextOutlined
} from '@ant-design/icons'
import dayjs from 'dayjs'
import { buildApiUrl, API_ENDPOINTS } from '../config/api'
import { formatTimestamp } from '../utils/dateUtils'
import './CoverageList.css'

const { Sider, Content } = Layout
const { RangePicker } = DatePicker
const { Title } = Typography

function CoverageList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [form] = Form.useForm()
  // 从URL参数读取语言，如果没有则默认为'go'
  const [selectedLanguage, setSelectedLanguage] = useState('go')
  const [diffCoverageData, setDiffCoverageData] = useState({}) // 存储增量覆盖率数据

  // 初始化时从URL参数读取语言，如果没有则设置默认值到URL
  useEffect(() => {
    const lang = searchParams.get('lang')
    if (lang && ['go', 'java', 'python'].includes(lang)) {
      setSelectedLanguage(lang)
    } else {
      // 如果URL中没有lang参数，设置默认值'go'到URL
      setSearchParams({ lang: 'go' }, { replace: true })
      setSelectedLanguage('go')
    }
  }, []) // 只在组件挂载时执行一次

  // 当URL参数变化时，更新selectedLanguage（排除初始化时的设置）
  useEffect(() => {
    const lang = searchParams.get('lang')
    if (lang && ['go', 'java', 'python'].includes(lang) && lang !== selectedLanguage) {
      setSelectedLanguage(lang)
    }
  }, [searchParams])

  useEffect(() => {
    fetchCoverageReports()
  }, [])

  const fetchCoverageReports = async (searchParams = {}) => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      
      const formValues = form.getFieldsValue()
      const repo = searchParams.repo !== undefined ? searchParams.repo : formValues.repo
      const branch = searchParams.branch !== undefined ? searchParams.branch : formValues.branch
      const createdAtRange = searchParams.createdAtRange !== undefined ? searchParams.createdAtRange : formValues.createdAtRange
      const updatedAtRange = searchParams.updatedAtRange !== undefined ? searchParams.updatedAtRange : formValues.updatedAtRange
      
      if (repo) {
        params.append('repo', repo)
      }
      if (branch) {
        params.append('branch', branch)
      }
      if (createdAtRange && Array.isArray(createdAtRange) && createdAtRange.length === 2 && createdAtRange[0] && createdAtRange[1]) {
        const start = dayjs(createdAtRange[0]).valueOf()
        const end = dayjs(createdAtRange[1]).valueOf()
        params.append('created_at_start', start.toString())
        params.append('created_at_end', end.toString())
      }
      if (updatedAtRange && Array.isArray(updatedAtRange) && updatedAtRange.length === 2 && updatedAtRange[0] && updatedAtRange[1]) {
        const start = dayjs(updatedAtRange[0]).valueOf()
        const end = dayjs(updatedAtRange[1]).valueOf()
        params.append('updated_at_start', start.toString())
        params.append('updated_at_end', end.toString())
      }
      
      const url = buildApiUrl(API_ENDPOINTS.REPORTS)
      const queryString = params.toString()
      const fullUrl = queryString ? `${url}?${queryString}` : url
      
      const response = await axios.get(fullUrl)
      const reportsList = response.data.data || []
      setReports(reportsList)
      message.success('数据加载成功')
      
      // 异步加载增量覆盖率数据
      loadDiffCoverageData(reportsList)
    } catch (err) {
      message.error(err.message || '获取数据失败')
      console.error('Error fetching coverage reports:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    fetchCoverageReports()
  }

  const handleReset = () => {
    form.resetFields()
    // 重置后立即搜索（使用空参数）
    setTimeout(() => {
      fetchCoverageReports({})
    }, 0)
  }

  // 加载增量覆盖率数据
  const loadDiffCoverageData = async (reportsList) => {
    const diffData = {}
    
    // 并发加载所有报告的增量覆盖率
    const promises = reportsList.map(async (report) => {
      try {
        const response = await axios.get(buildApiUrl(API_ENDPOINTS.DIFF_COVERAGE(report.id)))
        if (response.data && response.data.summary) {
          diffData[report.id] = response.data.summary
        }
      } catch (error) {
        console.warn(`Failed to load diff coverage for report ${report.id}:`, error)
        diffData[report.id] = null
      }
    })
    
    await Promise.allSettled(promises)
    setDiffCoverageData(diffData)
  }

  const formatCommit = (commit) => {
    if (!commit) return '-'
    return commit.length > 8 ? commit.substring(0, 8) + '...' : commit
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

  const columns = [
    {
      title: '仓库名称',
      dataIndex: 'repo_name',
      key: 'repo_name',
      width: 150,
      fixed: 'left',
      render: (text) => (
        <Tag color="blue" style={{ fontSize: '13px' }}>
          {text || '-'}
        </Tag>
      )
    },
    {
      title: '分支',
      dataIndex: 'branch',
      key: 'branch',
      width: 100
    },
    {
      title: 'Commit',
      dataIndex: 'commit',
      key: 'commit',
      width: 100,
      render: (text) => (
        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>
          {formatCommit(text)}
        </span>
      )
    },
    {
      title: '基准分支',
      dataIndex: 'base_branch',
      key: 'base_branch',
      width: 100,
      render: (text) => text || 'master'
    },
    {
      title: '基准 Commit',
      dataIndex: 'base_commit',
      key: 'base_commit',
      width: 100,
      render: (text) => (
        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>
          {text ? formatCommit(text) : '-'}
        </span>
      )
    },
    {
      title: '初始上报时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (text) => formatTimestamp(text)
    },
    {
      title: '最新上报时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 150,
      render: (text) => formatTimestamp(text)
    },
    {
      title: '全量覆盖率数据',
      children: [
        {
          title: '覆盖行',
          dataIndex: 'covered_statements',
          key: 'covered_statements',
          width: 90,
          align: 'right',
          render: (text) => (
            <span style={{ fontWeight: 500 }}>
              {text != null ? text.toLocaleString() : '-'}
            </span>
          )
        },
        {
          title: '总有效行',
          dataIndex: 'total_statements',
          key: 'total_statements',
          width: 90,
          align: 'right',
          render: (text) => (
            <span style={{ fontWeight: 500 }}>
              {text != null ? text.toLocaleString() : '-'}
            </span>
          )
        },
        {
          title: '覆盖率',
          dataIndex: 'coverage_rate',
          key: 'coverage_rate',
          width: 90,
          align: 'center',
          render: (text) => getCoverageTag(text)
        },
        {
          title: '操作',
          key: 'full_action',
          width: 60,
          align: 'center',
          render: (_, record) => (
            <Link to={`/detail/${record.id}?lang=${selectedLanguage}`}>
              <Button 
                type="link" 
                icon={<EyeOutlined />} 
                size="small"
                title="查看全量覆盖率详情"
              />
            </Link>
          )
        }
      ]
    },
    {
      title: '增量系统调测覆盖率数据',
      children: [
        {
          title: '新增已覆盖',
          key: 'diff_new_covered',
          width: 100,
          align: 'right',
          render: (_, record) => {
            const diffData = diffCoverageData[record.id]
            if (!diffData) {
              return <span style={{ color: '#999' }}>-</span>
            }
            return (
              <Link to={`/diff/${record.id}?lang=${selectedLanguage}`}>
                <span style={{ fontWeight: 500, color: '#1890ff', cursor: 'pointer' }}>
                  {diffData.new_covered_lines || 0}
                </span>
              </Link>
            )
          }
        },
        {
          title: '新增总行数',
          key: 'diff_total_new',
          width: 100,
          align: 'right',
          render: (_, record) => {
            const diffData = diffCoverageData[record.id]
            if (!diffData) {
              return <span style={{ color: '#999' }}>-</span>
            }
            return (
              <Link to={`/diff/${record.id}?lang=${selectedLanguage}`}>
                <span style={{ fontWeight: 500, color: '#1890ff', cursor: 'pointer' }}>
                  {diffData.total_new_lines || 0}
                </span>
              </Link>
            )
          }
        },
        {
          title: '覆盖率',
          key: 'diff_coverage_rate',
          width: 90,
          align: 'center',
          render: (_, record) => {
            const diffData = diffCoverageData[record.id]
            if (!diffData) {
              return <span style={{ color: '#999' }}>-</span>
            }
            const rate = diffData.incremental_coverage_rate || 0
            return (
              <Link to={`/diff/${record.id}?lang=${selectedLanguage}`}>
                {getCoverageTag(rate)}
              </Link>
            )
          }
        },
        {
          title: '操作',
          key: 'diff_action',
          width: 60,
          align: 'center',
          render: (_, record) => (
            <Link to={`/diff/${record.id}?lang=${selectedLanguage}`}>
              <Button 
                type="link" 
                icon={<EyeOutlined />} 
                size="small"
                title="查看增量覆盖率详情"
              />
            </Link>
          )
        }
      ]
    }
  ]

  const handleMenuClick = ({ key }) => {
    // 处理Config菜单项
    if (key.startsWith('config-')) {
      const language = key.replace('config-', '')
      window.location.href = `/config/${language}`
      return
    }
    
    // 更新URL参数和状态
    setSelectedLanguage(key)
    setSearchParams({ lang: key })
    // 切换语言时重新加载数据
    fetchCoverageReports({})
  }

  // 根据选中的语言过滤数据
  const filteredReports = reports.filter(report => {
    if (selectedLanguage === 'go') {
      // GO 语言：coverage_format 为 'goc' 或空
      return !report.coverage_format || report.coverage_format.toLowerCase() === 'goc' || report.coverage_format.toLowerCase() === 'go'
    } else if (selectedLanguage === 'java') {
      // JAVA 语言：coverage_format 为 'java' 或 'jacoco'
      return report.coverage_format && (report.coverage_format.toLowerCase() === 'java' || report.coverage_format.toLowerCase() === 'jacoco')
    } else if (selectedLanguage === 'python') {
      // Python 语言：coverage_format 为 'python'、'coverage'、'pyca' 或 'pca'（向后兼容）
      return report.coverage_format && (report.coverage_format.toLowerCase() === 'python' || report.coverage_format.toLowerCase() === 'coverage' || report.coverage_format.toLowerCase() === 'pyca' || report.coverage_format.toLowerCase() === 'pca')
    }
    return true
  })

  const menuItems = [
    {
      key: 'data',
      icon: <DatabaseOutlined />,
      label: 'Data',
      children: [
        {
          key: 'go',
          icon: <FileTextOutlined />,
          label: 'GO'
        },
        {
          key: 'java',
          icon: <FileTextOutlined />,
          label: 'JAVA'
        },
        {
          key: 'python',
          icon: <FileTextOutlined />,
          label: 'Python'
        }
      ]
    },
    {
      key: 'config',
      icon: <DatabaseOutlined />,
      label: 'Config',
      children: [
        {
          key: 'config-go',
          icon: <FileTextOutlined />,
          label: 'GO'
        },
        {
          key: 'config-java',
          icon: <FileTextOutlined />,
          label: 'JAVA'
        },
        {
          key: 'config-python',
          icon: <FileTextOutlined />,
          label: 'Python'
        }
      ]
    }
  ]

  return (
    <div className="coverage-list-container">
      <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
        {/* 左侧菜单栏 */}
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedLanguage]}
            defaultOpenKeys={['data', 'config']}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>

        {/* 右侧内容区域 */}
        <Layout style={{ background: '#f0f2f5' }}>
          <Content style={{ padding: '8px' }}>
            <Card>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                {/* 标题和刷新按钮 */}
                <Row justify="space-between" align="middle">
                  <Col>
                    <Title level={3} style={{ margin: 0 }}>
                      覆盖率报告列表
                    </Title>
                  </Col>
                  <Col>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={() => fetchCoverageReports()}
                      loading={loading}
                    >
                      刷新
                    </Button>
                  </Col>
                </Row>

          <Divider style={{ margin: '12px 0' }} />

          {/* 搜索表单 */}
          <Card size="small" style={{ background: '#fafafa' }}>
            <Form
              form={form}
              layout="vertical"
              onFinish={handleSearch}
            >
              <Row gutter={16}>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item label="仓库搜索" name="repo">
                    <Input
                      placeholder="输入仓库名称或链接"
                      allowClear
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item label="分支搜索" name="branch">
                    <Input
                      placeholder="输入分支名称"
                      allowClear
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item label="初始上报时间" name="createdAtRange">
                    <RangePicker
                      showTime
                      format="YYYY-MM-DD HH:mm:ss"
                      style={{ width: '100%' }}
                      placeholder={['开始时间', '结束时间']}
                    />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12} md={8} lg={6}>
                  <Form.Item label="最新上报时间" name="updatedAtRange">
                    <RangePicker
                      showTime
                      format="YYYY-MM-DD HH:mm:ss"
                      style={{ width: '100%' }}
                      placeholder={['开始时间', '结束时间']}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Row>
                <Col span={24} style={{ textAlign: 'right' }}>
                  <Space>
                    <Button onClick={handleReset}>
                      重置
                    </Button>
                    <Button
                      type="primary"
                      icon={<SearchOutlined />}
                      htmlType="submit"
                      loading={loading}
                    >
                      搜索
                    </Button>
                  </Space>
                </Col>
              </Row>
            </Form>
          </Card>

                {/* 数据表格 */}
                <Card>
                  <Table
                    columns={columns}
                    dataSource={filteredReports}
                    rowKey="id"
                    loading={loading}
                    scroll={{ x: 2200 }}
                    pagination={{
                      showSizeChanger: true,
                      showQuickJumper: true,
                      showTotal: (total) => `共 ${total} 条记录`,
                      pageSizeOptions: ['10', '20', '50', '100'],
                      defaultPageSize: 20
                    }}
                    locale={{
                      emptyText: '暂无覆盖率数据'
                    }}
                    size="middle"
                    bordered
                  />
                </Card>
              </Space>
            </Card>
          </Content>
        </Layout>
      </Layout>
    </div>
  )
}

export default CoverageList
