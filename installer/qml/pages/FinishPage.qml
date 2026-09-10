import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

ColumnLayout {
    id: page

    spacing: 0

    readonly property color accentColor: Coordinator.accentColor

    // ═══════════════════════════════════════════
    // Hero 区：图标 + 标题
    // ═══════════════════════════════════════════
    ColumnLayout {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 8
        spacing: Theme.spacingMd

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 200
            Layout.preferredHeight: 200
            source: FinishPresenter.finishIcon
            fillMode: Image.PreserveAspectFit
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "title"
            text: FinishPresenter.finishTitle
            color: accentColor
        }
    }

    // ═══════════════════════════════════════════
    // Content 卡片
    // ═══════════════════════════════════════════
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: 12
        Layout.bottomMargin: 12
        color: Theme.bgWhite
        radius: 8
        border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.25)
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: Theme.spacingMd

            ILabel {
                Layout.fillWidth: true
                labelType: "body"
                text: FinishPresenter.finishMessage
                lineHeight: 1.6
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignTop
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
    }

    // ═══════════════════════════════════════════
    // Actions 区
    // ═══════════════════════════════════════════
    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignRight

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