import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// qmllint disable unqualified

Dialog {
    id: root

    // 类型：info | warning | error | success
    property string msgType: "info"
    property string msgText: ""

    modal: true
    width: 380
    implicitHeight: contentLayout.implicitHeight + header.height + padding * 2
    anchors.centerIn: Overlay.overlay
    padding: 20

    title: {
        switch (msgType) {
        case "error": return "错误"
        case "warning": return "警告"
        case "success": return "成功"
        default: return "提示"
        }
    }

    function _accentColor() {
        switch (msgType) {
        case "error": return Theme.danger
        case "warning": return Theme.warning
        case "success": return Theme.success
        default: return Theme.info
        }
    }

    function _iconText() {
        switch (msgType) {
        case "error": return "✕"
        case "warning": return "!"
        case "success": return "✓"
        default: return "i"
        }
    }

    background: Rectangle {
        color: Theme.bgSecondary
        radius: Theme.radius
        border.color: Theme.border
    }

    header: Rectangle {
        color: root._accentColor()
        height: 38
        radius: Theme.radius

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.radius
            color: parent.color
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 10
            spacing: 8

            Rectangle {
                width: 22; height: 22; radius: 11
                color: Theme.bgPrimary

                Text {
                    anchors.centerIn: parent
                    text: root._iconText()
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: root._accentColor()
                }
            }

            Text {
                text: root.title
                font.family: Theme.fontFamily
                font.pixelSize: 14
                font.bold: true
                color: Theme.bgPrimary
            }

            Item { Layout.fillWidth: true }
        }
    }

    contentItem: ColumnLayout {
        id: contentLayout
        spacing: 20

        Text {
            id: msgLabel
            Layout.fillWidth: true
            text: root.msgText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textPrimary
            wrapMode: Text.WordWrap
            lineHeight: 1.5
        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }

            GButton {
                text: "确定"
                implicitWidth: 80
                colorType: {
                    switch (root.msgType) {
                    case "error": return "danger"
                    case "warning": return "warning"
                    case "success": return "success"
                    default: return "primary"
                    }
                }
                onClicked: root.accept()
            }
        }
    }
}