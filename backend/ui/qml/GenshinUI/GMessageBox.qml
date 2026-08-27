import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Dialog {
    id: root

    // 类型：info | warning | error | success
    property string msgType: "info"
    property string msgText: ""
    property bool closeOnOverlayClick: true

    modal: true
    closePolicy: closeOnOverlayClick
        ? Popup.CloseOnEscape | Popup.CloseOnPressOutside
        : Popup.CloseOnEscape
    width: 400
    anchors.centerIn: Overlay.overlay
    padding: 24

    // ========== 动画 ==========
    enter: Transition {
        NumberAnimation { target: root; property: "opacity"; from: 0; to: 1; duration: 200 }
    }
    exit: Transition {
        NumberAnimation { target: root; property: "opacity"; from: 1; to: 0; duration: 150 }
    }
    Overlay.modal: Rectangle {
        color: "#80000000"
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    // ========== 语义映射 ==========
    function _accentColor() {
        switch (msgType) {
        case "error": return Theme.danger
        case "warning": return Theme.warning
        case "success": return Theme.success
        default: return Theme.info
        }
    }

    function _barColor() {
        switch (msgType) {
        case "error": return Theme.dangerMedium
        case "warning": return Theme.warningMedium
        case "success": return Theme.successMedium
        default: return Theme.infoMedium
        }
    }

    function _iconBgColor() {
        switch (msgType) {
        case "error": return Theme.dangerLight
        case "warning": return Theme.warningLight
        case "success": return Theme.successLight
        default: return Theme.infoLight
        }
    }

    function _iconText() {
        switch (msgType) {
        case "error": return Icon.circleXmark
        case "warning": return Icon.exclamation
        case "success": return Icon.circleCheck
        default: return Icon.info
        }
    }

    title: {
        switch (msgType) {
        case "error": return "错误"
        case "warning": return "警告"
        case "success": return "成功"
        default: return "提示"
        }
    }

    // ========== 顶部强调色条（4px） ==========
    header: Item {
        implicitHeight: 4
        Rectangle {
            anchors.fill: parent
            color: root._barColor()
            radius: Theme.radius
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Theme.radius
                color: parent.color
            }
        }
    }

    // ========== 背景 ==========
    background: Rectangle {
        color: Theme.bgSecondary
        radius: Theme.radius
        border.color: Theme.border
    }

    // ========== 内容 ==========
    contentItem: ColumnLayout {
        spacing: 20

        // 图标 + 标题
        RowLayout {
            spacing: 16

            Rectangle {
                implicitWidth: 44; implicitHeight: 44; radius: 22
                color: root._iconBgColor()

                Text {
                    anchors.centerIn: parent
                    text: root._iconText()
                    font.family: Icon.fontSolid
                    font.pixelSize: 20
                    color: root._accentColor()
                }
            }

            Text {
                text: root.title
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.bold: true
                color: Theme.textPrimary
            }
        }

        // 消息正文
        Text {
            Layout.fillWidth: true
            Layout.leftMargin: 60
            text: root.msgText
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textSecondary
            wrapMode: Text.WordWrap
            lineHeight: 1.6
        }

        // 按钮
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