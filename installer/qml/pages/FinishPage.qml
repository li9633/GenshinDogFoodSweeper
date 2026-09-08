import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        // 图标
        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 36
            Layout.preferredHeight: 36
            source: FinishPresenter.finishIcon
            fillMode: Image.PreserveAspectFit
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: FinishPresenter.finishTitle
            color: Coordinator.accentColor
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: FinishPresenter.finishMessage
            lineHeight: 1.5
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "small"
            visible: FinishPresenter.showShortcutHint
            text: "可在桌面快捷方式中快速启动"
            color: Theme.subtleText
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
            onClicked: FinishPresenter.quit()
        }

        IButton {
            text: "启动程序"
            btnType: "primary"
            font.bold: true
            visible: FinishPresenter.showFinishLaunchButton
            onClicked: FinishPresenter.launchApp()
        }
    }
}