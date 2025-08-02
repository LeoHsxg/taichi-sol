import requests
import json


# 測試新的 FCM 格式
def test_new_fcm_format():
    """測試新的 FCM 格式（不包含 title，發送到 test_topic）"""

    # 你提供的 JSON 格式
    payload = {
        "message": {
            "token": "cz4Ztxr0S9eHopTQGzQWlB:APA91bGgbUo-av51o9Z-hwfPuy-VGAgunZhjAl6rri-xG2DzrVABvZqlrtqUNY23gWhANkN-7z9lYKQ09OpRe1XSf63QKnlgXx_dqn72FIQkXuSfW-dPq7s",
            "data": {
                "show_overlay": "true",
                "overlay_type": "type1",
                "overlay_message": "這是 Postman 測試的彈窗",
            },
            "topic": "test_topic",
        }
    }

    try:
        response = requests.post(
            "http://localhost:5000/api/send_fcm",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print("=== 測試新的 FCM 格式 ===")
        print(f"狀態碼: {response.status_code}")
        print(f"回應: {response.json()}")
        print()

    except Exception as e:
        print(f"測試失敗: {e}")


def test_old_fcm_format():
    """測試舊的 FCM 格式（包含 title）"""

    payload = {
        "title": "太極麻糬提醒你記得睡覺...",
        "body": "別再滑啦！該休息了！",
        "topic": "test_topic",
        "data": {"test_key": "test_value"},
    }

    try:
        response = requests.post(
            "http://localhost:5000/api/send_fcm",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        print("=== 測試舊的 FCM 格式 ===")
        print(f"狀態碼: {response.status_code}")
        print(f"回應: {response.json()}")
        print()

    except Exception as e:
        print(f"測試失敗: {e}")


def test_fcm_status():
    """測試 FCM 狀態檢查"""

    try:
        response = requests.get("http://localhost:5000/api/fcm_status")

        print("=== 測試 FCM 狀態 ===")
        print(f"狀態碼: {response.status_code}")
        print(f"回應: {response.json()}")
        print()

    except Exception as e:
        print(f"測試失敗: {e}")


if __name__ == "__main__":
    print("開始測試 FCM 功能...")
    print()

    # 測試 FCM 狀態
    test_fcm_status()

    # 測試新的 FCM 格式
    test_new_fcm_format()

    # 測試舊的 FCM 格式
    test_old_fcm_format()

    print("測試完成！")
