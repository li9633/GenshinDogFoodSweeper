import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// GameDetector 是 Python 通过 setContextProperty 注入的上下文属性

Rectangle {
    id: root
    Layout.fillWidth: true
    Layout.preferredHeight: 40
    color: "transparent"

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 8

        Text {
            text: "原神狗粮清扫器"
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.bold: true
            color: Theme.accent
        }

        Item { Layout.fillWidth: true }

        // 游戏运行状态
        RowLayout {
            spacing: 6

            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: GameDetector.isRunning ? Theme.success : Theme.danger
            }

            Text {
                text: GameDetector.isRunning ? "原神已启动" : "原神未启动"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
            }
        }
    }
}