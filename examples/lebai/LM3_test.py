"""
LM3 + L Master Docker 离线仿真：最小运动测试
前提：
  1) 你已启动 l-master docker，并能在 http://localhost/dashboard 登录
  2) pip install lebai-sdk
"""

import time
import lebai_sdk


def main():
    lebai_sdk.init()

    ip = "127.0.0.1"   # 本机 Docker 仿真
    simu = True        # 离线仿真模式

    arm = lebai_sdk.connect(ip, simu)

    if not arm.is_connected():
        raise RuntimeError("连接失败：请确认 docker 在跑、端口映射正常，并且 dashboard 可打开。")

    # 启动/上使能
    arm.start_sys()

    # （可选）读一下当前关节，确认通信正常
    try:
        q = arm.get_actual_joint()   # 若你的 SDK 版本没有该函数，删掉这几行即可
        print("Current joint:", q)
    except Exception as e:
        print("Skip get_actual_joint():", e)

    # 目标关节角（单位通常为 rad；6 轴）
    pose1 = [0.0, -1.0, 1.0, 0.0, 1.57, 0.0]
    pose2 = [0.4, -0.9, 1.2, -0.2, 1.57, 0.3]

    print("MoveJ -> pose1")
    arm.movej(pose1, a=0.6, v=0.3, t=0, r=0)
    arm.wait_move()

    time.sleep(0.5)

    print("MoveJ -> pose2")
    arm.movej(pose2, a=0.6, v=0.3, t=0, r=0)
    arm.wait_move()

    time.sleep(0.5)

    # 停机
    arm.stop_sys()
    print("Done.")


if __name__ == "__main__":
    main()

