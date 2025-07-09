import sys
import os
import time

# Add the parent directory of 'synchronous' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.server_info import get_ip_and_port
from ganzin.sol_sdk.synchronous.models import StreamingMode
from ganzin.sol_sdk.synchronous.sync_client import SyncClient
from ganzin.sol_sdk.streaming.gaze_stream import EyeStatus


def check_device_status(sc):
    """檢查設備狀態"""
    print("=" * 60)
    print("設備狀態檢查")
    print("=" * 60)

    try:
        # 獲取設備狀態
        status = sc.get_status()
        print(f"設備狀態: {status}")

        # 獲取場景攝影機參數
        params = sc.get_scene_camera_parameters()
        print(f"場景攝影機參數: {params}")

    except Exception as e:
        print(f"無法獲取設備狀態: {e}")


def check_gaze_data_quality(sc):
    """檢查視線數據品質"""
    print("\n" + "=" * 60)
    print("視線數據品質檢查")
    print("=" * 60)

    # 創建視線串流線程
    th = sc.create_streaming_thread(StreamingMode.GAZE)
    th.start()

    try:
        sample_count = 0
        valid_eye_detections = 0
        valid_pupil_detections = 0

        print("開始收集視線數據樣本...")
        print("請保持頭部穩定，直視前方")
        print("按 Ctrl+C 停止檢查")

        while sample_count < 100:  # 收集100個樣本
            gazes = sc.get_gazes_from_streaming(timeout=5.0)

            for gaze in gazes:
                sample_count += 1

                # 檢查眼睛檢測
                left_eye_status = gaze.left_eye.eye_status
                right_eye_status = gaze.right_eye.eye_status

                if (
                    left_eye_status == EyeStatus.NORMAL
                    or right_eye_status == EyeStatus.NORMAL
                ):
                    valid_eye_detections += 1

                # 檢查瞳孔檢測
                left_pupil_valid = gaze.left_eye.pupil3d.validity > 0.5
                right_pupil_valid = gaze.right_eye.pupil3d.validity > 0.5

                if left_pupil_valid or right_pupil_valid:
                    valid_pupil_detections += 1

                # 每10個樣本打印一次進度
                if sample_count % 10 == 0:
                    print(f"樣本 {sample_count}/100")
                    print(
                        f"  有效眼睛檢測: {valid_eye_detections}/{sample_count} ({valid_eye_detections/sample_count*100:.1f}%)"
                    )
                    print(
                        f"  有效瞳孔檢測: {valid_pupil_detections}/{sample_count} ({valid_pupil_detections/sample_count*100:.1f}%)"
                    )

                    # 顯示當前狀態
                    print(f"  左眼狀態: {left_eye_status.name}")
                    print(f"  右眼狀態: {right_eye_status.name}")
                    print(f"  左眼瞳孔有效性: {gaze.left_eye.pupil3d.validity:.3f}")
                    print(f"  右眼瞳孔有效性: {gaze.right_eye.pupil3d.validity:.3f}")
                    print()

                if sample_count >= 100:
                    break

    except KeyboardInterrupt:
        print("\n停止數據收集...")
    except Exception as e:
        print(f"錯誤: {e}")
    finally:
        th.cancel()
        th.join()

    # 打印最終結果
    print("\n" + "=" * 60)
    print("診斷結果")
    print("=" * 60)
    print(f"總樣本數: {sample_count}")
    print(f"有效眼睛檢測率: {valid_eye_detections/sample_count*100:.1f}%")
    print(f"有效瞳孔檢測率: {valid_pupil_detections/sample_count*100:.1f}%")

    if valid_eye_detections / sample_count < 0.1:
        print("\n⚠️  警告: 眼睛檢測率過低!")
        print("可能的原因:")
        print("1. 設備未正確校準")
        print("2. 頭部位置不正確")
        print("3. 光線條件不佳")
        print("4. 設備需要重新校準")
    else:
        print("\n✅ 眼睛檢測正常")

    if valid_pupil_detections / sample_count < 0.1:
        print("\n⚠️  警告: 瞳孔檢測率過低!")
        print("可能的原因:")
        print("1. 瞳孔追蹤未啟用")
        print("2. 設備配置問題")
        print("3. 需要重新校準")
    else:
        print("\n✅ 瞳孔檢測正常")


def provide_troubleshooting_tips():
    """提供故障排除建議"""
    print("\n" + "=" * 60)
    print("故障排除建議")
    print("=" * 60)
    print("如果檢測率過低，請嘗試以下步驟:")
    print()
    print("1. 設備校準:")
    print("   - 確保設備已正確校準")
    print("   - 重新進行校準程序")
    print("   - 檢查校準品質")
    print()
    print("2. 頭部位置:")
    print("   - 保持頭部穩定")
    print("   - 直視前方")
    print("   - 避免過度移動")
    print()
    print("3. 環境條件:")
    print("   - 確保光線充足但不過亮")
    print("   - 避免強光直射眼睛")
    print("   - 避免陰影遮擋眼睛")
    print()
    print("4. 設備設置:")
    print("   - 檢查設備連接")
    print("   - 確認軟體版本")
    print("   - 重新啟動設備")
    print()
    print("5. 瞳孔追蹤:")
    print("   - 確認瞳孔追蹤功能已啟用")
    print("   - 檢查設備配置")
    print("   - 可能需要特殊設置")


def main():
    address, port = get_ip_and_port()
    sc = SyncClient(address, port)

    print("Sol 設備診斷工具")
    print("此工具將幫助您檢查設備狀態和視線追蹤品質")
    print()

    # 檢查設備狀態
    check_device_status(sc)

    # 檢查視線數據品質
    check_gaze_data_quality(sc)

    # 提供故障排除建議
    provide_troubleshooting_tips()

    print("\n診斷完成!")


if __name__ == "__main__":
    main()
