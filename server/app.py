import sys
import os
import time
import threading
import json
import requests
from collections import deque
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, messaging

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.streaming.gaze_stream import EyeStatus

app = Flask(__name__)
CORS(app)


class BlinkAndPupilAnalyzer:
    def __init__(self, window_seconds=60):
        """
        初始化眨眼和瞳孔分析器

        Args:
            window_seconds (int): 分析時間窗口（秒）
        """
        self.window_seconds = window_seconds
        self.window_ms = window_seconds * 1000

        # 眨眼檢測相關
        self.left_eye_status_history = deque()
        self.right_eye_status_history = deque()
        self.blink_count = 0
        self.last_blink_time = None
        self.last_report_time = None

        # 邊緣觸發狀態追蹤
        self.was_blinking = False

        # 眨眼檢測參數
        self.blink_min_interval_ms = 300

        # 瞳孔大小相關
        self.left_pupil_sizes = deque()
        self.right_pupil_sizes = deque()
        self.left_pupil_validity = deque()
        self.right_pupil_validity = deque()

        # 統計數據
        self.start_time = None

    def add_gaze_data(self, gaze_data):
        """
        添加視線數據進行分析

        Args:
            gaze_data: GazeData 物件
        """
        if self.start_time is None:
            self.start_time = gaze_data.timestamp

        current_time = gaze_data.timestamp

        # 清理過期的數據
        self._cleanup_old_data(current_time)

        # 記錄眼睛狀態
        self._record_eye_status(gaze_data, current_time)

        # 記錄瞳孔大小
        self._record_pupil_size(gaze_data, current_time)

        # 檢測眨眼
        self._detect_blinks(gaze_data, current_time)

    def _cleanup_old_data(self, current_time):
        """清理超過時間窗口的舊數據"""
        cutoff_time = current_time - self.window_ms

        # 清理眼睛狀態歷史
        while (
            self.left_eye_status_history
            and self.left_eye_status_history[0][0] < cutoff_time
        ):
            self.left_eye_status_history.popleft()
        while (
            self.right_eye_status_history
            and self.right_eye_status_history[0][0] < cutoff_time
        ):
            self.right_eye_status_history.popleft()

        # 清理瞳孔大小歷史
        while self.left_pupil_sizes and self.left_pupil_sizes[0][0] < cutoff_time:
            self.left_pupil_sizes.popleft()
        while self.right_pupil_sizes and self.right_pupil_sizes[0][0] < cutoff_time:
            self.right_pupil_sizes.popleft()

        while self.left_pupil_validity and self.left_pupil_validity[0][0] < cutoff_time:
            self.left_pupil_validity.popleft()
        while (
            self.right_pupil_validity and self.right_pupil_validity[0][0] < cutoff_time
        ):
            self.right_pupil_validity.popleft()

    def _record_eye_status(self, gaze_data, current_time):
        """記錄眼睛狀態"""
        # 左眼狀態
        left_status = gaze_data.left_eye.eye_status
        self.left_eye_status_history.append((current_time, left_status))

        # 右眼狀態
        right_status = gaze_data.right_eye.eye_status
        self.right_eye_status_history.append((current_time, right_status))

    def _record_pupil_size(self, gaze_data, current_time):
        """記錄瞳孔大小"""
        # 左眼瞳孔
        if gaze_data.left_eye.pupil3d.validity > 0.5:
            self.left_pupil_sizes.append(
                (current_time, gaze_data.left_eye.pupil3d.diameter)
            )
            self.left_pupil_validity.append(
                (current_time, gaze_data.left_eye.pupil3d.validity)
            )

        # 右眼瞳孔
        if gaze_data.right_eye.pupil3d.validity > 0.5:
            self.right_pupil_sizes.append(
                (current_time, gaze_data.right_eye.pupil3d.diameter)
            )
            self.right_pupil_validity.append(
                (current_time, gaze_data.right_eye.pupil3d.validity)
            )

    def _detect_blinks(self, gaze_data, current_time):
        """檢測眨眼（邊緣觸發）"""
        left_status = gaze_data.left_eye.eye_status
        right_status = gaze_data.right_eye.eye_status

        # 邊緣觸發眨眼檢測邏輯
        current_is_blink = (
            left_status == EyeStatus.BLINK or right_status == EyeStatus.BLINK
        )

        # 如果當前狀態是眨眼，且之前不是眨眼狀態，則觸發眨眼事件
        if current_is_blink and not self.was_blinking:
            # 避免重複計算同一次眨眼
            if (
                self.last_blink_time is None
                or current_time - self.last_blink_time > self.blink_min_interval_ms
            ):
                self.blink_count += 1
                self.last_blink_time = current_time

        # 更新眨眼狀態
        self.was_blinking = current_is_blink

    def get_blink_frequency(self, current_time=None):
        """
        計算眨眼頻率（每分鐘眨眼次數）

        Args:
            current_time: 當前時間戳，用於計算時間窗口內的眨眼

        Returns:
            float: 眨眼頻率（次/分鐘）
        """
        if not self.left_eye_status_history:
            return 0.0

        if current_time is None:
            # 如果沒有指定時間，使用整個歷史數據
            window_duration_minutes = self.window_seconds / 60.0
            blink_frequency = self.blink_count / window_duration_minutes
            return blink_frequency

        # 簡化版本：使用總眨眼次數除以時間窗口
        window_duration_minutes = self.window_seconds / 60.0
        blink_frequency = self.blink_count / window_duration_minutes

        return blink_frequency

    def reset_for_new_report(self):
        """重製統計數據，準備新的報告週期"""
        self.blink_count = 0
        self.left_pupil_sizes.clear()
        self.right_pupil_sizes.clear()
        self.left_pupil_validity.clear()
        self.right_pupil_validity.clear()
        self.last_blink_time = None
        self.was_blinking = False

    def get_pupil_statistics(self):
        """
        獲取瞳孔大小統計數據

        Returns:
            dict: 包含左右眼瞳孔統計數據的字典
        """
        stats = {
            "left_eye": {
                "mean_diameter": 0.0,
                "min_diameter": 0.0,
                "max_diameter": 0.0,
                "valid_samples": 0,
                "validity_rate": 0.0,
            },
            "right_eye": {
                "mean_diameter": 0.0,
                "min_diameter": 0.0,
                "max_diameter": 0.0,
                "valid_samples": 0,
                "validity_rate": 0.0,
            },
        }

        # 左眼瞳孔統計
        if self.left_pupil_sizes:
            diameters = [size for _, size in self.left_pupil_sizes]
            stats["left_eye"]["mean_diameter"] = sum(diameters) / len(diameters)
            stats["left_eye"]["min_diameter"] = min(diameters)
            stats["left_eye"]["max_diameter"] = max(diameters)
            stats["left_eye"]["valid_samples"] = len(diameters)

        if self.left_pupil_validity:
            valid_count = sum(
                1 for _, validity in self.left_pupil_validity if validity > 0.5
            )
            stats["left_eye"]["validity_rate"] = (
                valid_count / len(self.left_pupil_validity) * 100
            )

        # 右眼瞳孔統計
        if self.right_pupil_sizes:
            diameters = [size for _, size in self.right_pupil_sizes]
            stats["right_eye"]["mean_diameter"] = sum(diameters) / len(diameters)
            stats["right_eye"]["min_diameter"] = min(diameters)
            stats["right_eye"]["max_diameter"] = max(diameters)
            stats["right_eye"]["valid_samples"] = len(diameters)

        if self.right_pupil_validity:
            valid_count = sum(
                1 for _, validity in self.right_pupil_validity if validity > 0.5
            )
            stats["right_eye"]["validity_rate"] = (
                valid_count / len(self.right_pupil_validity) * 100
            )

        return stats

    def get_current_pupil_sizes(self):
        """
        獲取最新的瞳孔大小

        Returns:
            dict: 當前左右眼瞳孔大小
        """
        current_sizes = {"left_eye": None, "right_eye": None}

        if self.left_pupil_sizes:
            current_sizes["left_eye"] = self.left_pupil_sizes[-1][1]

        if self.right_pupil_sizes:
            current_sizes["right_eye"] = self.right_pupil_sizes[-1][1]

        return current_sizes

    def get_analysis_data(self):
        """獲取分析數據用於 API 返回"""
        pupil_stats = self.get_pupil_statistics()
        current_sizes = self.get_current_pupil_sizes()
        blink_freq = self.get_blink_frequency()

        return {
            "blink_frequency": blink_freq,
            "blink_count": self.blink_count,
            "window_seconds": self.window_seconds,
            "pupil_statistics": pupil_stats,
            "current_pupil_sizes": current_sizes,
            "timestamp": datetime.now().isoformat(),
        }


class FCMNotifier:
    def __init__(self, service_account_path=None, project_id=None):
        """
        初始化 FCM 通知器 (使用 Firebase Admin SDK)

        Args:
            service_account_path (str): Firebase 服務帳戶金鑰檔案路徑
            project_id (str): Firebase 專案 ID
        """
        self.project_id = project_id
        self.app = None
        self._initialize_firebase(service_account_path)

    def _initialize_firebase(self, service_account_path):
        """初始化 Firebase Admin SDK"""
        try:
            if service_account_path and os.path.exists(service_account_path):
                # 使用服務帳戶金鑰檔案
                cred = credentials.Certificate(service_account_path)
                self.app = firebase_admin.initialize_app(cred)
                print(f"Firebase Admin SDK 已初始化 (使用服務帳戶檔案)")
            else:
                # 使用預設憑證 (環境變數或 Google Cloud 預設憑證)
                self.app = firebase_admin.initialize_app()
                print(f"Firebase Admin SDK 已初始化 (使用預設憑證)")
        except Exception as e:
            print(f"Firebase Admin SDK 初始化失敗: {e}")
            self.app = None

    def send_notification(
        self,
        title,
        body,
        data=None,
        topic=None,
        token=None,
        android_config=None,
        apns_config=None,
        webpush_config=None,
    ):
        """
        發送 FCM 通知 (使用 Firebase Admin SDK V1 API)

        Args:
            title (str): 通知標題
            body (str): 通知內容
            data (dict): 額外數據
            topic (str): 主題（用於主題訂閱）
            token (str): 設備令牌（用於單一設備）
            android_config (dict): Android 特定配置
            apns_config (dict): iOS 特定配置
            webpush_config (dict): Web 推送特定配置

        Returns:
            bool: 發送是否成功
        """
        if not self.app:
            print("Firebase Admin SDK 未初始化")
            return False

        try:
            # 構建通知訊息
            notification = messaging.Notification(title=title, body=body)

            # 構建訊息
            message = messaging.Message(
                notification=notification,
                data=data or {},
                android=android_config,
                apns=apns_config,
                webpush=webpush_config,
            )

            # 發送訊息
            if topic:
                # 發送到主題
                response = messaging.send_to_topic(topic, message)
                print(f"FCM 通知發送成功到主題 '{topic}': {title}")
            elif token:
                # 發送到單一設備
                response = messaging.send_to_token(token, message)
                print(f"FCM 通知發送成功到設備: {title}")
            else:
                # 預設發送到測試主題
                response = messaging.send_to_topic("test", message)
                print(f"FCM 通知發送成功到測試主題: {title}")

            return True

        except messaging.UnregisteredError as e:
            print(f"FCM 設備未註冊: {e}")
            return False
        except messaging.InvalidArgumentError as e:
            print(f"FCM 參數錯誤: {e}")
            return False
        except messaging.QuotaExceededError as e:
            print(f"FCM 配額超限: {e}")
            return False
        except messaging.ThirdPartyAuthError as e:
            print(f"FCM 第三方認證錯誤: {e}")
            return False
        except Exception as e:
            print(f"FCM 通知發送錯誤: {e}")
            return False

    def create_android_config(self, priority="high", ttl=None, collapse_key=None):
        """
        創建 Android 特定配置

        Args:
            priority (str): 優先級 ("normal" 或 "high")
            ttl (int): 生存時間（秒）
            collapse_key (str): 折疊鍵

        Returns:
            messaging.AndroidConfig: Android 配置物件
        """
        return messaging.AndroidConfig(
            priority=priority,
            ttl=ttl,
            collapse_key=collapse_key,
            notification=messaging.AndroidNotification(
                icon="ic_notification", color="#4CAF50", sound="default"
            ),
        )


class EyeTrackingServer:
    def __init__(self, service_account_path=None, project_id=None):
        """初始化眼動追蹤伺服器"""
        self.analyzer = BlinkAndPupilAnalyzer(window_seconds=15)
        self.fcm_notifier = FCMNotifier(service_account_path, project_id)
        self.is_running = False
        self.streaming_thread = None
        self.sync_client = None

        # 分析參數
        self.analysis_window_seconds = 15
        self.report_interval_seconds = 15
        self.blink_min_interval_ms = 400

        # 警報閾值
        self.blink_frequency_threshold = 20  # 每分鐘眨眼次數閾值
        self.pupil_size_threshold = 3.0  # 瞳孔大小閾值 (mm)
        self.validity_threshold = 50  # 有效性率閾值 (%)

    def start_tracking(self):
        """開始眼動追蹤"""
        if self.is_running:
            return {"status": "error", "message": "追蹤已在運行中"}

        try:
            address, port = get_ip_and_port()
            self.sync_client = SyncClient(address, port)

            # 設定分析器參數
            self.analyzer.window_seconds = self.analysis_window_seconds
            self.analyzer.blink_min_interval_ms = self.blink_min_interval_ms

            # 創建視線串流線程
            self.streaming_thread = self.sync_client.create_streaming_thread(
                StreamingMode.GAZE
            )
            self.streaming_thread.start()

            self.is_running = True

            # 啟動分析線程
            analysis_thread = threading.Thread(target=self._analysis_loop)
            analysis_thread.daemon = True
            analysis_thread.start()

            return {"status": "success", "message": "眼動追蹤已開始"}

        except Exception as e:
            return {"status": "error", "message": f"啟動失敗: {str(e)}"}

    def stop_tracking(self):
        """停止眼動追蹤"""
        if not self.is_running:
            return {"status": "error", "message": "追蹤未在運行"}

        try:
            self.is_running = False

            if self.streaming_thread:
                self.streaming_thread.cancel()
                self.streaming_thread.join()

            if self.sync_client:
                self.sync_client = None

            return {"status": "success", "message": "眼動追蹤已停止"}

        except Exception as e:
            return {"status": "error", "message": f"停止失敗: {str(e)}"}

    def _analysis_loop(self):
        """分析循環"""
        last_report_time = time.time()

        while self.is_running:
            try:
                gazes = self.sync_client.get_gazes_from_streaming(timeout=5.0)

                for gaze in gazes:
                    self.analyzer.add_gaze_data(gaze)

                    # 檢查是否需要發送警報
                    self._check_alerts()

                    # 按設定的間隔重製統計數據
                    current_time = time.time()
                    if current_time - last_report_time >= self.report_interval_seconds:
                        self.analyzer.reset_for_new_report()
                        last_report_time = current_time

            except Exception as e:
                print(f"分析循環錯誤: {e}")
                time.sleep(1)

    def _check_alerts(self):
        """檢查警報條件並發送 FCM 通知"""
        try:
            # 獲取當前分析數據
            analysis_data = self.analyzer.get_analysis_data()
            pupil_stats = analysis_data["pupil_statistics"]
            current_sizes = analysis_data["current_pupil_sizes"]

            # 檢查眨眼頻率
            if analysis_data["blink_frequency"] > self.blink_frequency_threshold:
                self.fcm_notifier.send_notification(
                    title="眨眼頻率警報",
                    body=f"眨眼頻率過高: {analysis_data['blink_frequency']:.1f} 次/分鐘",
                    data={
                        "type": "blink_frequency",
                        "value": analysis_data["blink_frequency"],
                        "threshold": self.blink_frequency_threshold,
                    },
                )

            # 檢查瞳孔大小
            for eye, size in current_sizes.items():
                if size and size < self.pupil_size_threshold:
                    self.fcm_notifier.send_notification(
                        title="瞳孔大小警報",
                        body=f"{eye} 瞳孔過小: {size:.2f} mm",
                        data={
                            "type": "pupil_size",
                            "eye": eye,
                            "value": size,
                            "threshold": self.pupil_size_threshold,
                        },
                    )

            # 檢查有效性率
            for eye, stats in pupil_stats.items():
                if stats["validity_rate"] < self.validity_threshold:
                    self.fcm_notifier.send_notification(
                        title="數據有效性警報",
                        body=f"{eye} 數據有效性過低: {stats['validity_rate']:.1f}%",
                        data={
                            "type": "validity_rate",
                            "eye": eye,
                            "value": stats["validity_rate"],
                            "threshold": self.validity_threshold,
                        },
                    )

        except Exception as e:
            print(f"警報檢查錯誤: {e}")

    def get_current_analysis(self):
        """獲取當前分析結果"""
        if not self.is_running:
            return {"status": "error", "message": "追蹤未在運行"}

        return {"status": "success", "data": self.analyzer.get_analysis_data()}

    def update_settings(self, settings):
        """更新設定"""
        try:
            if "analysis_window_seconds" in settings:
                self.analysis_window_seconds = settings["analysis_window_seconds"]
                self.analyzer.window_seconds = self.analysis_window_seconds

            if "report_interval_seconds" in settings:
                self.report_interval_seconds = settings["report_interval_seconds"]

            if "blink_min_interval_ms" in settings:
                self.blink_min_interval_ms = settings["blink_min_interval_ms"]
                self.analyzer.blink_min_interval_ms = self.blink_min_interval_ms

            if "blink_frequency_threshold" in settings:
                self.blink_frequency_threshold = settings["blink_frequency_threshold"]

            if "pupil_size_threshold" in settings:
                self.pupil_size_threshold = settings["pupil_size_threshold"]

            if "validity_threshold" in settings:
                self.validity_threshold = settings["validity_threshold"]

            return {"status": "success", "message": "設定已更新"}

        except Exception as e:
            return {"status": "error", "message": f"設定更新失敗: {str(e)}"}


# 創建全域伺服器實例
# 可以通過環境變數或直接指定 Firebase 配置
firebase_service_account = os.path.join(
    os.path.dirname(__file__), "utils", "service_account.json"
)
firebase_project_id = "taichi-mochi"

eye_tracking_server = EyeTrackingServer(
    service_account_path=firebase_service_account, project_id=firebase_project_id
)


@app.route("/")
def index():
    """主頁面"""
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start_tracking():
    """開始眼動追蹤"""
    result = eye_tracking_server.start_tracking()
    return jsonify(result)


@app.route("/api/stop", methods=["POST"])
def stop_tracking():
    """停止眼動追蹤"""
    result = eye_tracking_server.stop_tracking()
    return jsonify(result)


@app.route("/api/status")
def get_status():
    """獲取追蹤狀態"""
    return jsonify(
        {
            "is_running": eye_tracking_server.is_running,
            "analysis_data": eye_tracking_server.get_current_analysis(),
        }
    )


@app.route("/api/analysis")
def get_analysis():
    """獲取分析結果"""
    return jsonify(eye_tracking_server.get_current_analysis())


@app.route("/api/settings", methods=["GET", "POST"])
def manage_settings():
    """管理設定"""
    if request.method == "GET":
        return jsonify(
            {
                "analysis_window_seconds": eye_tracking_server.analysis_window_seconds,
                "report_interval_seconds": eye_tracking_server.report_interval_seconds,
                "blink_min_interval_ms": eye_tracking_server.blink_min_interval_ms,
                "blink_frequency_threshold": eye_tracking_server.blink_frequency_threshold,
                "pupil_size_threshold": eye_tracking_server.pupil_size_threshold,
                "validity_threshold": eye_tracking_server.validity_threshold,
            }
        )
    else:
        settings = request.json
        result = eye_tracking_server.update_settings(settings)
        return jsonify(result)


@app.route("/api/send_fcm", methods=["POST"])
def send_fcm_notification():
    """手動發送 FCM 通知"""
    try:
        data = request.json
        title = data.get("title", "測試通知")
        body = data.get("body", "這是一個測試通知")
        notification_data = data.get("data", {})
        topic = data.get("topic")
        token = data.get("token")

        # 平台特定配置
        android_config = None
        apns_config = None
        webpush_config = None

        if data.get("android_config"):
            android_config = eye_tracking_server.fcm_notifier.create_android_config(
                priority=data["android_config"].get("priority", "high"),
                ttl=data["android_config"].get("ttl"),
                collapse_key=data["android_config"].get("collapse_key"),
            )

        success = eye_tracking_server.fcm_notifier.send_notification(
            title=title,
            body=body,
            data=notification_data,
            topic=topic,
            token=token,
            android_config=android_config,
            apns_config=apns_config,
            webpush_config=webpush_config,
        )

        return jsonify(
            {
                "status": "success" if success else "error",
                "message": "FCM 通知已發送" if success else "FCM 通知發送失敗",
            }
        )

    except Exception as e:
        return jsonify({"status": "error", "message": f"發送失敗: {str(e)}"})


@app.route("/api/fcm_status")
def get_fcm_status():
    """獲取 FCM 狀態"""
    try:
        is_initialized = eye_tracking_server.fcm_notifier.app is not None
        return jsonify(
            {
                "status": "success",
                "fcm_initialized": is_initialized,
                "project_id": eye_tracking_server.fcm_notifier.project_id,
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"獲取狀態失敗: {str(e)}"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
