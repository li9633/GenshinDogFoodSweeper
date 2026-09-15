import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

ProgressBar {
    id: control

    // ============================================================
    // 公开属性
    // ============================================================
    property string progressText: ""

    Layout.preferredHeight: 18
    clip: true

    // ============================================================
    // 背景
    // ============================================================
    background: Rectangle {
        color: Theme.bgTrack
        radius: 4
    }

    // ============================================================
    // 内容区：进度条 + 动画 + 文字
    // ============================================================
    contentItem: Item {
        id: barContent

        // 确定进度条
        Rectangle {
            visible: !control.indeterminate
            width: control.visualPosition * barContent.width
            height: 6
            radius: 3
            color: Theme.accent
            anchors.verticalCenter: barContent.verticalCenter
        }

        // 不确定进度条（滚动动画）
        Rectangle {
            id: indeterminateBar
            visible: control.indeterminate
            width: barContent.width * 0.3
            height: 6
            radius: 3
            color: Theme.accent
            anchors.verticalCenter: barContent.verticalCenter
        }

        NumberAnimation {
            id: indeterminateAnim
            target: indeterminateBar
            property: "x"
            from: -indeterminateBar.width
            to: barContent.width
            duration: 1500
            loops: Animation.Infinite
        }

        // 显式控制动画启停
        // 关键：visible 从 false→true 时，布局在同一帧内尚未完成，
        // barContent.width 仍为 0。通过监听 onWidthChanged 在布局完成后
        // 重新尝试启动动画，确保 visible + indeterminate 同时变化时动画正常。
        Connections {
            target: control
            function onIndeterminateChanged() {
                barContent._syncAnimState()
            }
            function onVisibleChanged() {
                barContent._syncAnimState()
            }
        }

        onWidthChanged: _syncAnimState()

        function _syncAnimState() {
            if (control.indeterminate && control.visible && barContent.width > 0) {
                indeterminateBar.x = -indeterminateBar.width
                indeterminateAnim.start()
            } else {
                indeterminateAnim.stop()
                indeterminateBar.x = 0
            }
        }

        // 进度文字
        Text {
            text: control.progressText
            anchors.centerIn: barContent
            font.family: Theme.fontFamily
            font.pixelSize: 11
            color: Theme.textSecondary
            visible: control.progressText !== ""
        }
    }
}