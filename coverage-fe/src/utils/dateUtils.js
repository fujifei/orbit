/**
 * 日期时间工具函数
 * 用于处理毫秒级时间戳的格式化
 */

/**
 * 格式化毫秒时间戳为本地时间字符串
 * @param {number|string} timestamp - 毫秒级时间戳（可以是数字或字符串）
 * @param {string} locale - 语言环境，默认为 'zh-CN'
 * @returns {string} 格式化后的时间字符串，如果输入无效则返回 '-'
 */
export const formatTimestamp = (timestamp, locale = 'zh-CN') => {
  if (!timestamp) return '-'
  
  // 处理字符串类型的数字
  const ts = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp
  
  // 验证是否为有效数字
  if (isNaN(ts) || ts <= 0) return '-'
  
  // 如果是秒级时间戳（小于13位），转换为毫秒
  const milliseconds = ts < 10000000000 ? ts * 1000 : ts
  
  try {
    const date = new Date(milliseconds)
    // 验证日期是否有效
    if (isNaN(date.getTime())) return '-'
    return date.toLocaleString(locale)
  } catch (error) {
    console.error('Error formatting timestamp:', error, 'timestamp:', timestamp)
    return '-'
  }
}

/**
 * 格式化毫秒时间戳为日期字符串（不包含时间）
 * @param {number|string} timestamp - 毫秒级时间戳
 * @param {string} locale - 语言环境，默认为 'zh-CN'
 * @returns {string} 格式化后的日期字符串
 */
export const formatDateOnly = (timestamp, locale = 'zh-CN') => {
  if (!timestamp) return '-'
  
  const ts = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp
  if (isNaN(ts) || ts <= 0) return '-'
  
  const milliseconds = ts < 10000000000 ? ts * 1000 : ts
  
  try {
    const date = new Date(milliseconds)
    if (isNaN(date.getTime())) return '-'
    return date.toLocaleDateString(locale)
  } catch (error) {
    console.error('Error formatting date:', error)
    return '-'
  }
}

/**
 * 格式化毫秒时间戳为时间字符串（不包含日期）
 * @param {number|string} timestamp - 毫秒级时间戳
 * @param {string} locale - 语言环境，默认为 'zh-CN'
 * @returns {string} 格式化后的时间字符串
 */
export const formatTimeOnly = (timestamp, locale = 'zh-CN') => {
  if (!timestamp) return '-'
  
  const ts = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp
  if (isNaN(ts) || ts <= 0) return '-'
  
  const milliseconds = ts < 10000000000 ? ts * 1000 : ts
  
  try {
    const date = new Date(milliseconds)
    if (isNaN(date.getTime())) return '-'
    return date.toLocaleTimeString(locale)
  } catch (error) {
    console.error('Error formatting time:', error)
    return '-'
  }
}

/**
 * 格式化毫秒时间戳为相对时间（如：2小时前）
 * @param {number|string} timestamp - 毫秒级时间戳
 * @returns {string} 相对时间字符串
 */
export const formatRelativeTime = (timestamp) => {
  if (!timestamp) return '-'
  
  const ts = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp
  if (isNaN(ts) || ts <= 0) return '-'
  
  const milliseconds = ts < 10000000000 ? ts * 1000 : ts
  const now = Date.now()
  const diff = now - milliseconds
  
  if (diff < 0) return '未来'
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  
  // 超过一周，显示具体日期
  try {
    const date = new Date(milliseconds)
    if (isNaN(date.getTime())) return '-'
    return date.toLocaleDateString('zh-CN')
  } catch (error) {
    return '-'
  }
}

