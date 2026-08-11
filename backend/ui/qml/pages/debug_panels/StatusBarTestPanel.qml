import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Rectangle {
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    Flow {
        anchors.centerIn: parent
        spacing: 10
        width: Math.min(implicitWidth, parent.width - 32)

        Repeater {
            model: [
                { level: "INFO",     label: "信息 (灰)", btnColor: "#6B6E8A", textColor: "white" },
                { level: "SUCCESS",  label: "成功 (绿)", btnColor: "#4CAF50", textColor: "white" },
                { level: "WARNING",  label: "警告 (橙)", btnColor: "#FF9800", textColor: "white" },
                { level: "ERROR",    label: "错误 (红)", btnColor: "#EF5350", textColor: "white" },
                { level: "CRITICAL", label: "严重",      btnColor: "#C62828", textColor: "white" }
            ]

            Button {
                text: modelData.label
                implicitWidth: 100
                implicitHeight: 32
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: modelData.textColor
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: modelData.btnColor
                    radius: Theme.radius
                }
                onClicked: {
                    console.log("[调试] 状态栏颜色测试 — " + modelData.level)
                }
            }
        }
    }
}