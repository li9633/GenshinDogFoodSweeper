import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

ColumnLayout {
    id: page

    visible: WelcomePresenter.mode !== "uninstall" && !Coordinator.quickUpdate
    spacing: 0

    readonly property color accentColor: Coordinator.accentColor

    // ═══════════════════════════════════════════
    // Hero 区：图标 + 标题 + 版本号
    // ═══════════════════════════════════════════
    ColumnLayout {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 8
        spacing: Theme.spacingMd

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 200
            Layout.preferredHeight: 200
            source: WelcomePresenter.pageIcon
            fillMode: Image.PreserveAspectFit
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "title"
            visible: !WelcomePresenter.isUpdateMode
            text: WelcomePresenter.pageTitle
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            visible: WelcomePresenter.isUpdateMode
            text: WelcomePresenter.pageTitle
            color: "#4CAF50"
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "normal"
            visible: WelcomePresenter.versionLabel !== ""
            text: WelcomePresenter.versionLabel
            color: WelcomePresenter.isUpdateMode ? "#4CAF50" : Theme.secondaryText
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
        border.color: Theme.separator
        border.width: 1
        clip: true

        ILabel {
            anchors.fill: parent
            anchors.margins: 16
            labelType: "body"
            text: WelcomePresenter.welcomeText
            lineHeight: 1.6
            wrapMode: Text.WordWrap
            verticalAlignment: Text.AlignTop
        }
    }

    // ═══════════════════════════════════════════
    // Actions 区
    // ═══════════════════════════════════════════
    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignRight

        IButton {
            text: "取消"
            btnType: "flat"
            onClicked: WelcomePresenter.quit()
        }

        IButton {
            text: WelcomePresenter.actionButtonText
            btnType: "primary"
            font.bold: true
            onClicked: {
                WelcomePresenter.nextStep();
            }
        }
    }
}