# 眼動追蹤分析 Flask 伺服器

這是一個基於 Flask 的眼動追蹤分析系統，整合了眨眼檢測、瞳孔分析和 FCM 推送功能。

## 功能特色

- 🔍 **即時眼動追蹤分析**

  - 眨眼頻率監控
  - 瞳孔大小分析
  - 數據有效性檢查

- 📱 **智能警報系統**

  - FCM 推送通知
  - 可自定義警報閾值
  - 多種警報類型

- 🌐 **Web 介面**
  - 簡潔美觀的前端介面
  - 即時數據顯示
  - 一鍵控制功能

## 安裝與設定

### 1. 安裝依賴

```bash
pip install -r requirements_flask.txt
```

### 2. 設定 FCM

1. 在 Firebase Console 創建專案
2. 獲取 FCM 伺服器金鑰
3. 在 `app.py` 中替換 `YOUR_FCM_SERVER_KEY`

```python
# 在 FCMNotifier 類別中
self.server_key = "your_actual_fcm_server_key"
```

### 3. 啟動伺服器

```bash
python app.py
```

伺服器將在 `http://localhost:5000` 啟動

## API 端點

### 控制端點

- `POST /api/start` - 開始眼動追蹤
- `POST /api/stop` - 停止眼動追蹤
- `GET /api/status` - 獲取追蹤狀態
- `GET /api/analysis` - 獲取分析結果

### 設定端點

- `GET /api/settings` - 獲取當前設定
- `POST /api/settings` - 更新設定

### FCM 端點

- `POST /api/send_fcm` - 發送 FCM 通知

## 警報系統

系統會根據以下條件自動發送 FCM 通知：

### 眨眼頻率警報

- **觸發條件**: 眨眼頻率 > 20 次/分鐘
- **通知內容**: 眨眼頻率過高警告

### 瞳孔大小警報

- **觸發條件**: 瞳孔直徑 < 3.0 mm
- **通知內容**: 瞳孔過小警告

### 數據有效性警報

- **觸發條件**: 數據有效性 < 50%
- **通知內容**: 數據有效性過低警告

## 前端功能

### 控制面板

- 開始/停止追蹤按鈕
- 刷新分析按鈕
- 測試 FCM 按鈕
- 即時狀態顯示

### 分析顯示

- 眨眼頻率和次數
- 左右眼瞳孔統計
- 系統狀態監控
- 警報狀態顯示

### FCM 測試

- 自定義通知標題和內容
- 一鍵發送測試通知

## 自定義設定

可以通過 API 或直接修改代碼來調整以下參數：

```python
# 分析參數
analysis_window_seconds = 15      # 分析時間窗口
report_interval_seconds = 15      # 報告間隔
blink_min_interval_ms = 400       # 眨眼最小間隔

# 警報閾值
blink_frequency_threshold = 20    # 眨眼頻率閾值
pupil_size_threshold = 3.0        # 瞳孔大小閾值
validity_threshold = 50           # 有效性閾值
```

## 使用範例

### 1. 基本使用

1. 啟動伺服器
2. 開啟瀏覽器訪問 `http://localhost:5000`
3. 點擊「開始追蹤」按鈕
4. 觀察即時分析結果

### 2. 測試 FCM

1. 確保已設定正確的 FCM 伺服器金鑰
2. 點擊「測試 FCM」按鈕
3. 檢查手機是否收到通知

### 3. 自定義警報

1. 修改警報閾值
2. 重新啟動伺服器
3. 開始追蹤並觸發警報條件

## 注意事項

1. **FCM 設定**: 必須設定正確的 FCM 伺服器金鑰才能發送通知
2. **設備連接**: 確保眼動追蹤設備已正確連接
3. **網路連接**: FCM 推送需要網路連接
4. **權限設定**: 確保應用有足夠權限訪問設備

## 故障排除

### FCM 推送失敗

- 檢查伺服器金鑰是否正確
- 確認網路連接正常
- 檢查 Firebase 專案設定

### 追蹤無法啟動

- 檢查眼動追蹤設備連接
- 確認 SDK 版本相容性
- 檢查伺服器 IP 和端口設定

### 數據異常

- 調整警報閾值
- 檢查設備校準狀態
- 確認環境光線條件

## 技術架構

- **後端**: Flask + Python
- **前端**: HTML5 + CSS3 + JavaScript
- **眼動追蹤**: Ganzin Sol SDK
- **推送通知**: Firebase Cloud Messaging
- **數據分析**: 自定義分析算法

## 開發者資訊

- 基於 Ganzin Sol SDK v1.2.2
- 支援同步和異步模式
- 可擴展的模組化設計
- 完整的錯誤處理機制
