import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

ColumnLayout {
    id: page

    spacing: 0

    readonly property color dangerColor: "#D32F2F"

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
            source: ConfirmPresenter.pageIcon
            fillMode: Image.PreserveAspectFit
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "title"
            text: ConfirmPresenter.pageTitle
            color: dangerColor
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
        color: "#FFF3F3"
        radius: 8
        border.color: "#FFCDD2"
        border.width: 1
        clip: true

        ILabel {
            anchors.fill: parent
            anchors.margins: 16
            labelType: "body"
            text: ConfirmPresenter.warningText
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
            text: "我再想想"
            btnType: "flat"
            onClicked: ConfirmPresenter.quit()
        }

        IButton {
            text: ConfirmPresenter.actionButtonText
            btnType: "danger"
            font.bold: true
            onClicked: {
                ConfirmPresenter.startUninstall();
            }
        }
    }
}