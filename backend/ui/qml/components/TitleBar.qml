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
        acceptedButtons: Qt.LeftButton
        onPressed: root.Window.window.startSystemMove()
        onDoubleClicked: {
            if (root.Window.window.visibility === Window.Maximized)
                root.Window.window.showNormal()
            else
                root.Window.window.showMaximized()
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
            icon: root.Window.window.visibility === Window.Maximized ? Icon.windowRestore : Icon.windowMaximize
            iconFont: Icon.fontRegular
            onClicked: {
                if (root.Window.window.visibility === Window.Maximized)
                    root.Window.window.showNormal()
                else
                    root.Window.window.showMaximized()
            }
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