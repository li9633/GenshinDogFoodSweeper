import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import '../InstallerUI'

// qmllint disable unqualified
Item {
    id: page

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "✓"
            font.pixelSize: Theme.fontSizeIcon
            color: Theme.success
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: InstallerPresenter.finishTitle
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: InstallerPresenter.finishMessage
        }

        // 创建桌面快捷方式提示
        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "small"
            visible: InstallerPresenter.showShortcutHint
            text: "已创建桌面快捷方式，双击即可启动。"
        }

        Item { Layout.fillHeight: true }
    }

    // 底部按钮
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.bottomMargin: Theme.spacingMd

        IButton {
            text: "关闭"
            btnType: "flat"
            onClicked: InstallerPresenter.quit()
        }

        IButton {
            text: "启动程序"
            btnType: "primary"
            font.bold: true
            onClicked: InstallerPresenter.launchApp()
        }
    }
}