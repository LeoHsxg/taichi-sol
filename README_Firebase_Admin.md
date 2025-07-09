# 眼動追蹤分析系統 - Firebase Admin SDK 版本

這是一個使用 Firebase Admin SDK 和 Firebase Cloud Messaging API (V1) 的眼動追蹤分析系統。

## 🚀 新功能特色

### 🔥 Firebase Admin SDK 整合

- **更安全的認證**: 使用服務帳戶金鑰而非伺服器金鑰
- **V1 API 支援**: 使用最新的 Firebase Cloud Messaging API
- **多平台支援**: Android、iOS、Web 推送配置
- **多播通知**: 支援同時發送給多個設備
- **錯誤處理**: 完整的錯誤處理和重試機制

### 📱 增強的 FCM 功能

- **平台特定配置**: Android、iOS、Web 推送的專用設定
- **多播通知**: 一次發送給多個設備
- **主題訂閱**: 支援 Firebase 主題訂閱
- **設備令牌管理**: 單一設備通知
- **通知優先級**: 可設定高優先級通知

## 📋 安裝與設定

### 1. 安裝依賴

```bash
pip install -r requirements_flask.txt
```

### 2. Firebase 專案設定

#### 步驟 1: 創建 Firebase 專案

1. 前往 [Firebase Console](https://console.firebase.google.com/)
2. 創建新專案或選擇現有專案
3. 啟用 Cloud Messaging 服務

#### 步驟 2: 生成服務帳戶金鑰

1. 在 Firebase Console 中，前往「專案設定」
2. 點擊「服務帳戶」標籤
3. 點擊「生成新的私鑰」
4. 下載 JSON 檔案並保存為 `firebase-service-account.json`

#### 步驟 3: 設定環境變數

創建 `.env` 檔案：

```env
# Firebase 設定
FIREBASE_SERVICE_ACCOUNT_PATH=./firebase-service-account.json
FIREBASE_PROJECT_ID=your-project-id

# Flask 設定
FLASK_ENV=development
FLASK_DEBUG=True

# 眼動追蹤設定
ANALYSIS_WINDOW_SECONDS=15
REPORT_INTERVAL_SECONDS=15
BLINK_MIN_INTERVAL_MS=400

# 警報閾值
BLINK_FREQUENCY_THRESHOLD=20
PUPIL_SIZE_THRESHOLD=3.0
VALIDITY_THRESHOLD=50
```

### 3. 啟動伺服器

```bash
python app.py
```

## 🔧 API 端點

### FCM 相關端點

#### 1. 發送單一通知

```http
POST /api/send_fcm
```

**請求範例**:

```json
{
  "title": "眼動追蹤警報",
  "body": "眨眼頻率過高",
  "data": {
    "type": "blink_frequency",
    "value": 25.5
  },
  "topic": "alerts",
  "token": "device_token_here",
  "android_config": {
    "priority": "high",
    "ttl": 3600,
    "collapse_key": "blink_alert"
  },
  "apns_config": {
    "badge": 1,
    "sound": "default"
  },
  "webpush_config": {
    "title": "Web 警報",
    "body": "Web 版本通知",
    "icon": "https://example.com/icon.png"
  }
}
```

#### 2. 發送多播通知

```http
POST /api/send_multicast_fcm
```

**請求範例**:

```json
{
  "tokens": ["token1", "token2", "token3"],
  "title": "群組通知",
  "body": "這是一個群組通知",
  "data": {
    "type": "group_alert"
  },
  "android_config": {
    "priority": "high"
  }
}
```

#### 3. 檢查 FCM 狀態

```http
GET /api/fcm_status
```

**回應範例**:

```json
{
  "status": "success",
  "fcm_initialized": true,
  "project_id": "your-project-id"
}
```

### 其他端點

- `POST /api/start` - 開始眼動追蹤
- `POST /api/stop` - 停止眼動追蹤
- `GET /api/status` - 獲取追蹤狀態
- `GET /api/analysis` - 獲取分析結果
- `GET /api/settings` - 獲取設定
- `POST /api/settings` - 更新設定

## 📱 平台特定配置

### Android 配置

```python
android_config = {
    "priority": "high",        # "normal" 或 "high"
    "ttl": 3600,              # 生存時間（秒）
    "collapse_key": "alert"   # 折疊鍵
}
```

### iOS 配置

```python
apns_config = {
    "badge": 1,               # 徽章數字
    "sound": "default"        # 聲音檔案名
}
```

### Web 推送配置

```python
webpush_config = {
    "title": "Web 通知標題",
    "body": "Web 通知內容",
    "icon": "https://example.com/icon.png"
}
```

## 🔔 警報系統

系統會根據以下條件自動發送 FCM 通知：

### 眨眼頻率警報

- **觸發條件**: 眨眼頻率 > 20 次/分鐘
- **通知內容**: 眨眼頻率過高警告
- **平台**: 支援所有平台

### 瞳孔大小警報

- **觸發條件**: 瞳孔直徑 < 3.0 mm
- **通知內容**: 瞳孔過小警告
- **平台**: 支援所有平台

### 數據有效性警報

- **觸發條件**: 數據有效性 < 50%
- **通知內容**: 數據有效性過低警告
- **平台**: 支援所有平台

## 🛠️ 使用範例

### 1. 基本使用

```python
# 發送簡單通知
response = requests.post('http://localhost:5000/api/send_fcm', json={
    "title": "測試通知",
    "body": "這是一個測試",
    "topic": "test"
})
```

### 2. 多播通知

```python
# 發送給多個設備
response = requests.post('http://localhost:5000/api/send_multicast_fcm', json={
    "tokens": ["token1", "token2", "token3"],
    "title": "群組通知",
    "body": "發送給所有設備"
})
```

### 3. 平台特定通知

```python
# Android 高優先級通知
response = requests.post('http://localhost:5000/api/send_fcm', json={
    "title": "緊急警報",
    "body": "需要立即注意",
    "android_config": {
        "priority": "high",
        "ttl": 3600
    }
})
```

## 🔒 安全性

### 認證方式

- **服務帳戶金鑰**: 比伺服器金鑰更安全
- **環境變數**: 敏感資訊不寫入程式碼
- **專案隔離**: 每個專案獨立的認證

### 最佳實踐

1. 將服務帳戶金鑰檔案放在安全位置
2. 使用環境變數管理敏感資訊
3. 定期輪換服務帳戶金鑰
4. 限制 FCM 使用配額

## 🐛 故障排除

### FCM 初始化失敗

```bash
# 檢查服務帳戶檔案
ls -la firebase-service-account.json

# 檢查環境變數
echo $FIREBASE_SERVICE_ACCOUNT_PATH
echo $FIREBASE_PROJECT_ID
```

### 通知發送失敗

- 檢查設備令牌是否有效
- 確認主題是否已訂閱
- 檢查 Firebase 專案設定
- 查看伺服器日誌

### 常見錯誤

- `UnregisteredError`: 設備令牌無效
- `InvalidArgumentError`: 參數格式錯誤
- `QuotaExceededError`: 配額超限
- `ThirdPartyAuthError`: 認證錯誤

## 📊 監控與日誌

### 日誌記錄

系統會記錄以下資訊：

- FCM 初始化狀態
- 通知發送結果
- 錯誤詳情
- 成功/失敗統計

### 監控端點

- `/api/fcm_status`: 檢查 FCM 狀態
- `/api/status`: 檢查整體系統狀態

## 🔄 升級指南

### 從舊版本升級

1. 安裝新的依賴: `pip install firebase-admin==6.2.0`
2. 設定 Firebase 專案和服務帳戶
3. 更新環境變數
4. 重新啟動伺服器

### 遷移注意事項

- 舊的伺服器金鑰方式已棄用
- 新的 API 提供更好的錯誤處理
- 支援更多平台特定功能

## 📞 支援

如有問題，請檢查：

1. Firebase Console 設定
2. 服務帳戶金鑰檔案
3. 環境變數設定
4. 網路連接狀態
5. 伺服器日誌

## 📄 授權

本專案基於 MIT 授權條款。
