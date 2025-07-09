import sys
import os
import time
from collections import deque
from datetime import datetime, timedelta

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.streaming.gaze_stream import EyeStatus


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
        self.last_report_time = None  # 上次報告時間

        # 邊緣觸發狀態追蹤
        self.was_blinking = False  # 追蹤前一個時刻是否在眨眼

        # 眨眼檢測參數
        self.blink_min_interval_ms = 300  # 默認300ms

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
        if gaze_data.left_eye.pupil3d.validity > 0.5:  # 有效性閾值
            self.left_pupil_sizes.append(
                (current_time, gaze_data.left_eye.pupil3d.diameter)
            )
            self.left_pupil_validity.append(
                (current_time, gaze_data.left_eye.pupil3d.validity)
            )

        # 右眼瞳孔
        if gaze_data.right_eye.pupil3d.validity > 0.5:  # 有效性閾值
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
        # 檢測從非眨眼狀態轉換到眨眼狀態的邊緣
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

        # 計算時間窗口內的眨眼次數
        cutoff_time = current_time - self.window_ms
        window_blink_count = 0

        # 統計時間窗口內的眨眼
        for timestamp, _ in self.left_eye_status_history:
            if timestamp >= cutoff_time:
                pass

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
        self.was_blinking = False  # 重置邊緣觸發狀態

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

    def print_analysis(self):
        """打印分析結果"""
        print("\n" + "=" * 60)
        print("眨眼和瞳孔分析報告")
        print("=" * 60)

        # 顯示檢測設定
        print(f"最小間隔: {self.blink_min_interval_ms}ms")

        # 眨眼頻率
        blink_freq = self.get_blink_frequency()
        print(f"眨眼頻率: {blink_freq:.1f} 次/分鐘")
        print(f"時間窗口: {self.window_seconds} 秒")
        print(f"眨眼次數: {self.blink_count}")

        # 瞳孔統計
        pupil_stats = self.get_pupil_statistics()
        current_sizes = self.get_current_pupil_sizes()

        print("\n瞳孔大小統計:")
        print("-" * 40)

        # 左眼
        left_stats = pupil_stats["left_eye"]
        print(f"左眼:")
        print(f"  平均直徑: {left_stats['mean_diameter']:.2f} mm")
        print(f"  最小直徑: {left_stats['min_diameter']:.2f} mm")
        print(f"  最大直徑: {left_stats['max_diameter']:.2f} mm")
        print(f"  有效樣本: {left_stats['valid_samples']}")
        print(f"  有效性率: {left_stats['validity_rate']:.1f}%")
        if current_sizes["left_eye"]:
            print(f"  當前直徑: {current_sizes['left_eye']:.2f} mm")

        # 右眼
        right_stats = pupil_stats["right_eye"]
        print(f"右眼:")
        print(f"  平均直徑: {right_stats['mean_diameter']:.2f} mm")
        print(f"  最小直徑: {right_stats['min_diameter']:.2f} mm")
        print(f"  最大直徑: {right_stats['max_diameter']:.2f} mm")
        print(f"  有效樣本: {right_stats['valid_samples']}")
        print(f"  有效性率: {right_stats['validity_rate']:.1f}%")
        if current_sizes["right_eye"]:
            print(f"  當前直徑: {current_sizes['right_eye']:.2f} mm")

        print("=" * 60)


def main():
    # ===== 可調整的參數 =====
    ANALYSIS_WINDOW_SECONDS = 15  # 分析時間窗口（秒）
    REPORT_INTERVAL_SECONDS = 15  # 報告間隔（秒）
    BLINK_MIN_INTERVAL_MS = 400  # 眨眼最小間隔（毫秒）
    # ========================

    address, port = get_ip_and_port()
    sc = SyncClient(address, port)

    # 創建分析器，使用設定的分析窗口
    analyzer = BlinkAndPupilAnalyzer(window_seconds=ANALYSIS_WINDOW_SECONDS)

    # 設定眨眼檢測參數
    analyzer.blink_min_interval_ms = BLINK_MIN_INTERVAL_MS

    print("開始眨眼和瞳孔分析...")
    print("按 Ctrl+C 停止分析")
    print(f"分析窗口: {ANALYSIS_WINDOW_SECONDS} 秒")
    print(f"報告頻率: 每{REPORT_INTERVAL_SECONDS}秒顯示一次")

    # 創建視線串流線程
    th = sc.create_streaming_thread(StreamingMode.GAZE)
    th.start()

    try:
        last_print_time = time.time()

        while True:
            gazes = sc.get_gazes_from_streaming(timeout=5.0)

            for gaze in gazes:
                # 添加數據到分析器
                analyzer.add_gaze_data(gaze)

                # 按設定的間隔打印分析結果
                current_time = time.time()
                if current_time - last_print_time >= REPORT_INTERVAL_SECONDS:
                    analyzer.print_analysis()
                    last_print_time = current_time

                    # 重製統計數據，準備下一個報告週期
                    analyzer.reset_for_new_report()

    except KeyboardInterrupt:
        print("\n停止分析...")
    except Exception as ex:
        print(f"錯誤: {ex}")
    finally:
        # 打印最終分析結果
        analyzer.print_analysis()

        th.cancel()
        th.join()
        print("分析完成")


if __name__ == "__main__":
    main()
