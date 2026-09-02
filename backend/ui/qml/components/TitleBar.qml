import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Rectangle {
    id: root
    Layout.fillWidth: true
    Layout.preferredHeight: 36
    color: Theme.bgSidebar

    // ============================================================
    // 拖拽区域（双击最大化/还原）
    // ============================================================
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.Window.window.startSystemMove()
        }
        onReleased: function(mouse) {
            // TODO: 右键菜单有 bug，临时禁用
            // if (mouse.button === Qt.RightButton)
            //     sysMenu.popup()
        }
        onDoubleClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                TitleBarPresenter.toggleMaximize()
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 4
        spacing: 0

        // 应用图标
        Image {
            width: 18; height: 18
            source: SettingsPresenter.appIconPath
            sourceSize.width: 18
            sourceSize.height: 18
            fillMode: Image.PreserveAspectFit
            Layout.alignment: Qt.AlignVCenter
        }

        // 标题
        Text {
            text: TitleBarPresenter.title
            font.family: Theme.fontFamily
            font.pixelSize: 13
            color: Theme.textSecondary
            Layout.leftMargin: 8
            Layout.alignment: Qt.AlignVCenter
        }

        Item { Layout.fillWidth: true }

        // 主题切换
        TitleBarButton {
            icon: Icon.circleHalfStroke
            iconFont: Icon.fontSolid
            onClicked: SettingsPresenter.setTheme(Theme.isDark ? "light" : "dark")
        }

        // 最小化到托盘
        TitleBarButton {
            icon: Icon.anglesDown
            iconFont: Icon.fontSolid
            onClicked: TitleBarPresenter.minimizeToTray()
        }

        // 最小化
        TitleBarButton {
            icon: Icon.minus
            iconFont: Icon.fontSolid
            onClicked: root.Window.window.showMinimized()
        }

        // 最大化/还原
        TitleBarButton {
            icon: TitleBarPresenter.maximized ? Icon.windowRestore : Icon.windowMaximize
            iconFont: Icon.fontRegular
            onClicked: TitleBarPresenter.toggleMaximize()
        }

        // 关闭
        TitleBarButton {
            icon: Icon.close
            iconFont: Icon.fontSolid
            isClose: true
            onClicked: root.Window.window.close()
        }
    }

    // ============================================================
    // 右键系统菜单
    // ============================================================
    Menu {
        id: sysMenu

        background: Rectangle {
            implicitWidth: 140
            radius: Theme.radius
            color: Theme.bgCard
            border.color: Theme.border
        }

        delegate: MenuItem {
            id: menuItem
            implicitWidth: 140
            implicitHeight: 30

            contentItem: Text {
                text: menuItem.text
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: menuItem.enabled ? Theme.textPrimary : Theme.textMuted
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }

            background: Rectangle {
                radius: 4
                color: menuItem.highlighted ? Theme.accentOverlay6 : "transparent"
            }
        }

        MenuItem {
            text: "还原"
            enabled: TitleBarPresenter.maximized
            onTriggered: TitleBarPresenter.toggleMaximize()
        }
        MenuItem {
            text: "移动"
            onTriggered: root.Window.window.startSystemMove()
        }
        MenuItem {
            text: "大小"
            onTriggered: root.Window.window.startSystemResize(Qt.BottomEdge | Qt.RightEdge)
        }
        MenuItem {
            text: "最小化"
            onTriggered: root.Window.window.showMinimized()
        }
        MenuItem {
            text: "最大化"
            enabled: !TitleBarPresenter.maximized
            onTriggered: TitleBarPresenter.toggleMaximize()
        }
        MenuSeparator {
            contentItem: Rectangle {
                implicitHeight: 1
                color: Theme.border
            }
        }
        MenuItem {
            text: "关闭\tAlt+F4"
            onTriggered: root.Window.window.close()
        }
    }

    // ============================================================
    // 内联按钮组件
    // ============================================================
    component TitleBarButton: Rectangle {
        width: 46
        height: 36
        color: _btnColor()
        property bool isClose: false
        property string icon: ""
        property string iconFont: Icon.fontRegular
        signal clicked()

        function _btnColor() {
            if (isClose && btnMouse.pressed) return Theme.dangerDeep
            if (isClose && btnMouse.containsMouse) return Theme.danger
            if (btnMouse.pressed) return Theme.accentOverlay10
            if (btnMouse.containsMouse) return Theme.accentOverlay6
            return "transparent"
        }

        Text {
            anchors.centerIn: parent
            text: parent.icon
            font.family: parent.iconFont
            font.pixelSize: 12
            color: parent.isClose && btnMouse.containsMouse ? "#FFFFFF" : Theme.textSecondary
        }

        MouseArea {
            id: btnMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: parent.clicked()
        }
    }
}