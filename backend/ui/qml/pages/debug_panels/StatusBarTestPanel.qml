// qmllint disable unqualified
import QtQuick
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
                { level: "INFO",     label: "信息 (灰)", btnColor: "#6B6E8A" },
                { level: "SUCCESS",  label: "成功 (绿)", btnColor: "#4CAF50" },
                { level: "WARNING",  label: "警告 (橙)", btnColor: "#FF9800" },
                { level: "ERROR",    label: "错误 (红)", btnColor: "#EF5350" },
                { level: "CRITICAL", label: "严重",      btnColor: "#C62828" }
            ]

            GButton {
                // modelData 是 Repeater delegate 的隐式上下文属性
                text: modelData.label
                btnColor: modelData.btnColor
                implicitWidth: 100
                implicitHeight: 32
                onClicked: StatusBarTest.testLog(modelData.level)
            }
        }
    }
}