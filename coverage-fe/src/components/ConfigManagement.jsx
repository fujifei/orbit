import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  Layout,
  Menu,
  Table,
  Card,
  Button,
  Space,
  Modal,
  Form,
  Input,
  message,
  Typography,
  Popconfirm,
  Tag
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  SettingOutlined,
  FileTextOutlined,
  DatabaseOutlined
} from '@ant-design/icons'
import { buildApiUrl, API_ENDPOINTS } from '../config/api'
import { formatTimestamp } from '../utils/dateUtils'
import './ConfigManagement.css'

const { Title } = Typography
const { TextArea } = Input
const { Sider, Content } = Layout

function ConfigManagement({ language }) {
  const navigate = useNavigate()
  const [configs, setConfigs] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [modalType, setModalType] = useState('create') // 'create' or 'edit'
  const [currentConfig, setCurrentConfig] = useState(null)
  const [form] = Form.useForm()
  const [loadingRepoId, setLoadingRepoId] = useState(false)

  useEffect(() => {
    fetchConfigs()
  }, [language])

  // 根据语言获取对应的 repo_type 值
  const getRepoType = (lang) => {
    const typeMap = {
      'go': 1,
      'python': 2,
      'java': 3
    }
    return typeMap[lang] || 1
  }

  // 根据语言获取排除文件后缀的placeholder
  const getExcludeFilesPlaceholder = (lang) => {
    const placeholderMap = {
      'go': '*._test.go;active_test.go',
      'python': '*_test.py;test_*.py',
      'java': '*Test.java;*Tests.java'
    }
    return placeholderMap[lang] || '*._test.go;active_test.go'
  }

  // 根据仓库链接自动获取RepoID
  const fetchRepoId = async (repoUrl) => {
    if (!repoUrl || !repoUrl.trim()) {
      return
    }

    // 验证仓库链接格式
    const httpsPattern = /^https?:\/\/.+\.git$/
    const sshPattern = /^git@.+:.+\.git$/
    
    if (!httpsPattern.test(repoUrl) && !sshPattern.test(repoUrl)) {
      return
    }

    try {
      setLoadingRepoId(true)
      const url = buildApiUrl(API_ENDPOINTS.GET_REPO_ID)
      const response = await axios.post(url, { repo_url: repoUrl })
      
      if (response.data.success && response.data.data?.repo_id) {
        form.setFieldsValue({ repo_id: response.data.data.repo_id })
      }
    } catch (err) {
      console.error('Error fetching repo_id:', err)
      // 不显示错误消息，让用户手动输入
    } finally {
      setLoadingRepoId(false)
    }
  }

  const fetchConfigs = async () => {
    try {
      setLoading(true)
      const repoType = getRepoType(language)
      const url = buildApiUrl(`${API_ENDPOINTS.CONFIGS}?repo_type=${repoType}`)
      const response = await axios.get(url)
      setConfigs(response.data.data || [])
    } catch (err) {
      message.error('获取配置列表失败: ' + (err.message || '未知错误'))
      console.error('Error fetching configs:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = () => {
    setModalType('create')
    setCurrentConfig(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = (record) => {
    setModalType('edit')
    setCurrentConfig(record)
    form.setFieldsValue({
      repo_url: record.repo_url,
      repo_id: record.repo_id,
      base_branch: record.base_branch,
      exclude_dirs: record.exclude_dirs,
      exclude_files: record.exclude_files
    })
    setModalVisible(true)
  }

  const handleDelete = async (repoId) => {
    try {
      const url = buildApiUrl(API_ENDPOINTS.CONFIG_DETAIL(repoId))
      await axios.delete(url)
      message.success('删除成功')
      fetchConfigs()
    } catch (err) {
      message.error('删除失败: ' + (err.response?.data?.error || err.message))
      console.error('Error deleting config:', err)
    }
  }

  const handleModalOk = async () => {
    try {
      const values = await form.validateFields()
      
      if (modalType === 'create') {
        // 创建时添加 repo_type 字段
        const repoType = getRepoType(language)
        const createData = {
          ...values,
          repo_type: repoType
        }
        const url = buildApiUrl(API_ENDPOINTS.CONFIGS)
        await axios.post(url, createData)
        message.success('创建成功')
      } else {
        // 编辑
        const url = buildApiUrl(API_ENDPOINTS.CONFIG_DETAIL(currentConfig.repo_id))
        // 编辑时只传递可编辑的字段
        const updateData = {
          base_branch: values.base_branch,
          exclude_dirs: values.exclude_dirs,
          exclude_files: values.exclude_files
        }
        await axios.put(url, updateData)
        message.success('更新成功')
      }
      
      setModalVisible(false)
      form.resetFields()
      fetchConfigs()
    } catch (err) {
      if (err.errorFields) {
        // 表单验证错误
        return
      }
      message.error((modalType === 'create' ? '创建' : '更新') + '失败: ' + 
        (err.response?.data?.error || err.message))
      console.error('Error saving config:', err)
    }
  }

  const handleModalCancel = () => {
    setModalVisible(false)
    form.resetFields()
  }

  const columns = [
    {
      title: '序号',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      fixed: 'left'
    },
    {
      title: 'RepoID',
      dataIndex: 'repo_id',
      key: 'repo_id',
      width: 120,
      fixed: 'left',
      render: (text) => (
        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>
          {text || '-'}
        </span>
      )
    },
    {
      title: '仓库名称',
      dataIndex: 'repo_name',
      key: 'repo_name',
      width: 150,
      render: (text) => (
        <Tag color="blue">{text}</Tag>
      )
    },
    {
      title: '仓库链接',
      dataIndex: 'repo_url',
      key: 'repo_url',
      width: 300,
      ellipsis: {
        showTitle: false
      },
      render: (text) => (
        <span style={{ fontFamily: 'monospace', fontSize: '12px' }} title={text}>
          {text}
        </span>
      )
    },
    {
      title: '基准分支',
      dataIndex: 'base_branch',
      key: 'base_branch',
      width: 120
    },
    {
      title: '覆盖率排除目录',
      dataIndex: 'exclude_dirs',
      key: 'exclude_dirs',
      width: 200,
      render: (text) => (
        <span style={{ fontSize: '12px', color: '#666' }}>
          {text || '-'}
        </span>
      )
    },
    {
      title: '覆盖率排除文件后缀',
      dataIndex: 'exclude_files',
      key: 'exclude_files',
      width: 200,
      render: (text) => (
        <span style={{ fontSize: '12px', color: '#666' }}>
          {text || '-'}
        </span>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text) => formatTimestamp(text)
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            size="small"
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个仓库配置吗？"
            onConfirm={() => handleDelete(record.repo_id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              size="small"
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  const handleMenuClick = ({ key }) => {
    // 处理 Data 菜单项 - 返回列表页
    if (key === 'go' || key === 'java' || key === 'python') {
      navigate('/')
      return
    }
    
    // 处理 Config 菜单项
    if (key.startsWith('config-')) {
      const lang = key.replace('config-', '')
      navigate(`/config/${lang}`)
      return
    }
  }

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
      icon: <SettingOutlined />,
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
    <div className="config-management-container">
      <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
        {/* 左侧菜单栏 */}
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[`config-${language}`]}
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
                {/* 标题和操作按钮 */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Title level={3} style={{ margin: 0 }}>
                    仓库配置管理 - {language.toUpperCase()}
                  </Title>
                  <Space>
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={fetchConfigs}
                      loading={loading}
                    >
                      刷新
                    </Button>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={handleCreate}
                    >
                      新增仓库
                    </Button>
                  </Space>
                </div>

                {/* 数据表格 */}
                <Table
                  columns={columns}
                  dataSource={configs}
                  rowKey="id"
                  loading={loading}
                  scroll={{ x: 1500 }}
                  pagination={{
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条记录`,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    defaultPageSize: 20
                  }}
                  locale={{
                    emptyText: '暂无配置数据'
                  }}
                  size="middle"
                  bordered
                />
              </Space>
            </Card>
          </Content>
        </Layout>
      </Layout>

      {/* 创建/编辑模态框 */}
      <Modal
        title={modalType === 'create' ? '新增仓库配置' : '编辑仓库配置'}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={handleModalCancel}
        width={600}
        okText="确定"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Form.Item
            label="仓库链接"
            name="repo_url"
            rules={[
              { required: true, message: '请输入仓库链接' },
              { 
                validator: (_, value) => {
                  if (!value) {
                    return Promise.resolve()
                  }
                  const httpsPattern = /^https?:\/\/.+\.git$/
                  const sshPattern = /^git@.+:.+\.git$/
                  if (httpsPattern.test(value) || sshPattern.test(value)) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('仓库链接格式不正确（支持 https:// 或 git@ 格式，需要以.git结尾）'))
                }
              }
            ]}
            extra="例如: https://github.com/fujifei/tuna.git 或 git@github.com:fujifei/tuna.git"
            tooltip="仓库名称会自动从链接中提取，RepoID会自动获取"
          >
            <Input 
              placeholder="https://github.com/fujifei/tuna.git 或 git@github.com:fujifei/tuna.git" 
              disabled={modalType === 'edit'}
              onBlur={(e) => {
                if (modalType === 'create' && e.target.value) {
                  fetchRepoId(e.target.value)
                }
              }}
            />
          </Form.Item>

          <Form.Item
            label="RepoID"
            name="repo_id"
            rules={[{ required: true, message: '请输入RepoID' }]}
            extra="仓库唯一标识（输入仓库链接后会自动获取）"
          >
            <Input 
              placeholder="输入仓库链接后自动获取" 
              disabled={modalType === 'edit'}
              suffix={loadingRepoId ? <span style={{ color: '#999', fontSize: '12px' }}>获取中...</span> : null}
            />
          </Form.Item>

          <Form.Item
            label="基准分支"
            name="base_branch"
            rules={[{ required: true, message: '请输入基准分支' }]}
            initialValue="master"
          >
            <Input placeholder="master" />
          </Form.Item>

          <Form.Item
            label="覆盖率排除目录"
            name="exclude_dirs"
            extra="多个目录用分号分隔，例如: cmd/;config/"
          >
            <TextArea
              placeholder="cmd/;config/"
              rows={3}
            />
          </Form.Item>

          <Form.Item
            label="覆盖率排除文件后缀"
            name="exclude_files"
            extra={`多个后缀用分号分隔，支持通配符，例如: ${getExcludeFilesPlaceholder(language)}`}
          >
            <TextArea
              placeholder={getExcludeFilesPlaceholder(language)}
              rows={3}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ConfigManagement

