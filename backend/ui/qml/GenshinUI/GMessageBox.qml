import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Popup {
    id: root

    // ========== 公开 API（与 Dialog 兼容） ==========
    property string title: ""
    property string msgType: "info"
    property string msgText: ""
    property bool bringToFront: false
    property bool closeOnOverlayClick: true
    property var buttonModel: []

    // 信号
    signal accepted()
    signal rejected()
    signal buttonClicked(string role)

    function accept() { close() }

    parent: Overlay.overlay
    x: Math.round((parent.width - width) / 2)
    y: Math.round((parent.height - height) / 2)
    width: 400
    modal: true
    closePolicy: closeOnOverlayClick
        ? Popup.CloseOnEscape | Popup.CloseOnPressOutside
        : Popup.CloseOnEscape
    padding: 0

    // 动画结束后关闭 layer，恢复文字次像素渲染
    onOpened: contentItem.layer.enabled = false
    onClosed: contentItem.layer.enabled = false

    Overlay.modal: Rectangle {
        color: "#80000000"
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }

    enter: Transition {
        SequentialAnimation {
            PropertyAction { target: root.contentItem; property: "layer.enabled"; value: true }
            ParallelAnimation {
                NumberAnimation {
                    target: root.contentItem; property: "scale"
                    from: 0.85; to: 1; duration: 300
                    easing.type: Easing.OutBack; easing.overshoot: 0.3
                }
                NumberAnimation { target: root; property: "opacity"; from: 0; to: 1; duration: 200 }
            }
        }
    }
    exit: Transition {
        SequentialAnimation {
            PropertyAction { target: root.contentItem; property: "layer.enabled"; value: true }
            ParallelAnimation {
                NumberAnimation { target: root.contentItem; property: "scale"; from: 1; to: 0.85; duration: 200 }
                NumberAnimation { target: root; property: "opacity"; from: 1; to: 0; duration: 150 }
            }
        }
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

    function _title() {
        if (title !== "") return title
        switch (msgType) {
        case "error": return "错误"
        case "warning": return "警告"
        case "success": return "成功"
        default: return "提示"
        }
    }

    // ========== 卡片背景（独立层，不受 contentItem.scale 影响） ==========
    background: Rectangle {
        color: Theme.bgSecondary
        radius: Theme.radius
        border.color: Theme.border

        // 顶部强调色条（始终 4px，不随动画缩放）
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 4
            color: root._barColor()
            radius: Theme.radius
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.radius
                color: parent.color
            }
        }
    }

    // ========== 内容（参与 scale 动画） ==========
    contentItem: Item {
        implicitHeight: contentLayout.implicitHeight + 28 + 24

        ColumnLayout {
            id: contentLayout
            anchors.fill: parent
            anchors.margins: 24
            anchors.topMargin: 28
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
                    text: root._title()
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

                // 默认按钮（无自定义按钮时）
                GButton {
                    visible: root.buttonModel.length === 0
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
                    onClicked: {
                        root.buttonClicked("accept")
                        root.accepted()
                        root.accept()
                    }
                }

                // 自定义按钮（从 buttonModel 动态渲染）
                Repeater {
                    model: root.buttonModel
                    GButton {
                        required property var modelData
                        visible: root.buttonModel.length > 0
                        text: modelData.text || ""
                        implicitWidth: 80
                        colorType: modelData.colorType || "primary"
                        onClicked: {
                            const role = modelData.role || ""
                            root.buttonClicked(role)
                            if (role === "accept") root.accepted()
                            else if (role === "reject") root.rejected()
                            root.close()
                        }
                    }
                }
            }
        }
    }
}