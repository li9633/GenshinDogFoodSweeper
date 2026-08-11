import QtQuick
import QtQuick.Controls
import GenshinUI

Rectangle {
    color: Theme.bgPrimary

    Column {
        anchors.centerIn: parent
        spacing: 12

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "圣遗物锁定器"
            font.family: Theme.fontFamily
            font.pixelSize: 22
            font.bold: true
            color: Theme.accent
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "圣遗物锁定功能将在后续版本实现"
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textSecondary
        }
    }
}