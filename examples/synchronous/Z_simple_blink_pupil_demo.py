import sys
import os
import time

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.streaming.gaze_stream import EyeStatus


def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)

    print("開始監測眨眼狀態和瞳孔大小...")
    print("按 Ctrl+C 停止")
    print("-" * 80)

    # 創建視線串流線程
    th = sc.create_streaming_thread(StreamingMode.GAZE)
    th.start()

    # 眨眼計數器
    blink_count = 0
    last_blink_time = None

    try:
        while True:
            gazes = sc.get_gazes_from_streaming(timeout=5.0)

            for gaze in gazes:
                current_time = gaze.timestamp

                # 1. 取得眼睛狀態
                left_eye_status = gaze.left_eye.eye_status
                right_eye_status = gaze.right_eye.eye_status

                # 2. 取得瞳孔大小（3D直徑，單位：毫米）
                left_pupil_diameter = gaze.left_eye.pupil3d.diameter
                right_pupil_diameter = gaze.right_eye.pupil3d.diameter
                left_pupil_validity = gaze.left_eye.pupil3d.validity
                right_pupil_validity = gaze.right_eye.pupil3d.validity

                # 3. 取得瞳孔2D位置（像素座標）
                left_pupil_x = gaze.left_eye.pupil2d.x
                left_pupil_y = gaze.left_eye.pupil2d.y
                right_pupil_x = gaze.right_eye.pupil2d.x
                right_pupil_y = gaze.right_eye.pupil2d.y

                # 4. 檢測眨眼
                if (
                    left_eye_status == EyeStatus.BLINK
                    or right_eye_status == EyeStatus.BLINK
                ):
                    # 避免重複計算同一次眨眼（200ms內只計算一次）
                    if last_blink_time is None or current_time - last_blink_time > 200:
                        blink_count += 1
                        last_blink_time = current_time

                # 5. 打印結果
                print(f"\n時間戳: {current_time}")
                print(f"眨眼次數: {blink_count}")
                print(f"左眼狀態: {left_eye_status.name} ({left_eye_status.value})")
                print(f"右眼狀態: {right_eye_status.name} ({right_eye_status.value})")

                # 瞳孔大小（只在有效性高時顯示）
                print("瞳孔大小 (mm):")
                if left_pupil_validity > 0.5:
                    print(
                        f"  左眼: {left_pupil_diameter:.2f} (有效性: {left_pupil_validity:.2f})"
                    )
                else:
                    print(f"  左眼: 無效數據 (有效性: {left_pupil_validity:.2f})")

                if right_pupil_validity > 0.5:
                    print(
                        f"  右眼: {right_pupil_diameter:.2f} (有效性: {right_pupil_validity:.2f})"
                    )
                else:
                    print(f"  右眼: 無效數據 (有效性: {right_pupil_validity:.2f})")

                # 瞳孔2D位置
                print("瞳孔2D位置 (像素):")
                print(f"  左眼: ({left_pupil_x:.1f}, {left_pupil_y:.1f})")
                print(f"  右眼: ({right_pupil_x:.1f}, {right_pupil_y:.1f})")

                # 視線位置
                if gaze.combined.gaze_2d.validity:
                    print(
                        f"視線位置: ({gaze.combined.gaze_2d.x:.1f}, {gaze.combined.gaze_2d.y:.1f})"
                    )
                else:
                    print("視線位置: 無效")

                print("-" * 80)

                # 控制輸出頻率
                time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n停止監測...")
    except Exception as ex:
        print(f"錯誤: {ex}")
    finally:
        th.cancel()
        th.join()
        print("監測完成")


def print_eye_status_info():
    """打印眼睛狀態的說明"""
    print("眼睛狀態說明:")
    print(f"  NO_EYE ({EyeStatus.NO_EYE.value}): 無法檢測到眼睛")
    print(f"  BLINK ({EyeStatus.BLINK.value}): 眨眼狀態")
    print(f"  NORMAL ({EyeStatus.NORMAL.value}): 正常狀態")
    print()


if __name__ == "__main__":
    print_eye_status_info()
    main()
